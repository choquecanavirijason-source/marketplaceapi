import os
import shutil
import subprocess
import tempfile
import uuid
from typing import Optional

from fastapi import HTTPException, UploadFile

from app.config.settings import settings

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v"}
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_VIDEO_SIZE_BYTES = 80 * 1024 * 1024  # 80 MB


def _remux_faststart(filepath: str) -> None:
    """Remuxea el video a MP4 progresivo con el moov al inicio (faststart).

    Videos "descargados de YouTube" con ciertas herramientas vienen
    fragmentados (moof/mdat repetidos, moov chico al inicio sin duración
    real) — reproducen bien en un reproductor de escritorio, pero en
    ExoPlayer/AVPlayer (apps móviles) la duración queda en 0 y el seek no
    funciona. Sin recodificar (-c copy), solo reordena/desfragmenta.
    No-op si ffmpeg no está instalado (ej. dev local sin ffmpeg) — el video
    queda como se subió, igual que antes de este fix."""
    if not shutil.which("ffmpeg"):
        return
    fd, tmp_path = tempfile.mkstemp(suffix=os.path.splitext(filepath)[1], dir=os.path.dirname(filepath))
    os.close(fd)
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", filepath, "-c", "copy", "-movflags", "+faststart", tmp_path],
            capture_output=True,
            timeout=120,
        )
        if result.returncode == 0 and os.path.getsize(tmp_path) > 0:
            os.replace(tmp_path, filepath)
        else:
            os.remove(tmp_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# Dos calidades alcanza para este volumen de uso — "low" para conexiones
# lentas, "high" para wifi/datos buenos. force_original_aspect_ratio=decrease
# respeta la orientación real del video (funciona igual para reels verticales
# que para tutoriales horizontales) sin estirarlo ni recortarlo.
#
# "high" usa max_dim 1920 — con un celular grabando a 1080x1920 (portrait,
# lo normal en reels), eso significa que NO se reduce resolución, solo se
# recomprime.
#
# Se usa CRF (calidad constante) en vez de bitrate fijo — en vez de decirle
# a ffmpeg "usá tantos kbps sí o sí" (que desperdicia bits en escenas simples
# y le faltan en escenas con movimiento, perdiendo nitidez ahí), se le pide
# "mantené esta calidad visual" y usa los bits que haga falta. crf 18 es
# considerado "visualmente sin pérdida" para H.264. v_maxrate/v_bufsize
# quedan solo como techo de seguridad (necesario para streaming) — no bajan
# la calidad real (eso lo sigue haciendo el CRF), pero si quedan demasiado
# altos, en datos móviles el reproductor tarda en juntar buffer y se nota
# como "carga lenta" aunque la conexión no sea tan mala.
HLS_RENDITIONS = [
    {"name": "low", "max_dim": 720, "crf": "23", "v_maxrate": "1500k", "v_bufsize": "2200k", "a_bitrate": "128k", "bandwidth": 1700000},
    {"name": "high", "max_dim": 1920, "crf": "18", "v_maxrate": "4000k", "v_bufsize": "6000k", "a_bitrate": "160k", "bandwidth": 4300000},
]

# Reels no usan streaming adaptativo (single MP4, ver _compress_single_video)
# — a diferencia de HLS, acá no hay una calidad "low" a la que el
# reproductor pueda bajar solo si la conexión no da abasto: esta es la
# ÚNICA calidad que se sirve. Historial de ajustes en esta VPS/conexión:
#   1080p/CRF24/1800kbps -> cargaba fluido pero tardaba demasiado en
#     bufferear en datos móviles ("a tirones" mientras carga).
#   640px/CRF27/700kbps  -> carga fluida, pero se ve pixelado/con poca
#     nitidez (resolución y bits por pixel ambos muy bajos).
#   720px/CRF25/1100kbps -> carga fluida y se ve bien, confirmado en el
#     celular real. Se sube un poco más la calidad (mismo max_dim, solo más
#     bits) para ver si sigue aguantando sin cortarse.
REEL_RENDITION = {"max_dim": 720, "crf": "23", "v_maxrate": "1400k", "v_bufsize": "2200k", "a_bitrate": "112k"}


def _is_hdr_source(source_path: str) -> bool:
    """Detecta si el video de origen es HDR (HLG o PQ/HDR10) — típico del
    modo "Video HDR" que activan solo por defecto varios iPhone. Si se
    transcodifica sin avisarle a ffmpeg, el resultado queda marcado como
    color de 10 bits (High 10 Profile), que la mayoría de los celulares
    Android NO puede decodificar en hardware — el video ni siquiera arranca."""
    if not shutil.which("ffprobe"):
        return False
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=color_transfer",
                "-of", "csv=p=0", source_path,
            ],
            capture_output=True,
            timeout=30,
            text=True,
        )
        transfer = result.stdout.strip().lower()
        return transfer in {"arib-std-b67", "smpte2084"}  # HLG / PQ (HDR10)
    except Exception:
        return False


def _generate_hls(source_path: str, out_dir: str) -> bool:
    """Genera streaming adaptativo (HLS) del video en dos calidades, como
    hacen YouTube/TikTok — el reproductor va pidiendo el archivo de a pocos
    segundos en vez de bajar el video entero, y baja de calidad solo si la
    conexión no da abasto. Antes servíamos el .mp4 pesado entero de una,
    por eso reels de videos "pesados" se veían lentos/trabados con internet
    limitado. No-op (devuelve False) si ffmpeg no está instalado."""
    if not shutil.which("ffmpeg"):
        return False
    is_hdr = _is_hdr_source(source_path)
    try:
        for rendition in HLS_RENDITIONS:
            # force_divisible_by=2: libx264 exige ancho/alto pares — sin esto,
            # un video vertical (ej. 1080x1920) escalado a un box de 720
            # puede dar un ancho impar (405) y ffmpeg tira "width not
            # divisible by 2", aborta, y el video cae al .mov crudo de
            # respaldo (que ni siquiera reproduce bien en el celular).
            scale = f"scale='min({rendition['max_dim']},iw)':'min({rendition['max_dim']},ih)':force_original_aspect_ratio=decrease:force_divisible_by=2"
            if is_hdr:
                # HDR (HLG/PQ) -> SDR de verdad, no solo "sacarle la etiqueta"
                # (eso dejaría los colores planos/lavados porque los valores
                # de píxel siguen siendo de una curva HLG interpretados como
                # si fueran bt709). zscale+tonemap hace la conversión real.
                video_filter = (
                    "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
                    "tonemap=tonemap=hable:desat=0,"
                    f"zscale=t=bt709:m=bt709:r=tv,format=yuv420p,{scale}"
                )
            else:
                video_filter = scale
            result = subprocess.run(
                [
                    "ffmpeg", "-y", "-i", source_path,
                    "-vf", video_filter,
                    "-pix_fmt", "yuv420p",
                    # fps_mode cfr SIN forzar -r: deja el frame rate constante
                    # (arregla timestamps irregulares de video con frame rate
                    # variable) pero respeta el fps real de la fuente — antes
                    # forzábamos 30fps fijo, y un video grabado a 60fps se
                    # veía notoriamente menos fluido que el original sin
                    # necesidad (el bug real que rompía la reproducción era
                    # otro: color HDR y ancho impar, ya arreglados aparte).
                    "-fps_mode", "cfr",
                    # "medium" (no "slow"): el VPS de producción es bastante
                    # más lento que una PC de desarrollo — con "slow" tardaba
                    # más de 5 minutos y el timeout del proxy cortaba antes
                    # de terminar (el video se terminaba de crear igual, pero
                    # ya se había mostrado el error). "medium" es notablemente
                    # más rápido con una pérdida de calidad mínima (el CRF
                    # sigue siendo el que manda la calidad real, esto solo
                    # afecta qué tan a fondo busca la mejor compresión).
                    "-c:v", "libx264", "-preset", "medium",
                    "-crf", rendition["crf"], "-maxrate", rendition["v_maxrate"], "-bufsize", rendition["v_bufsize"],
                    "-g", "48", "-keyint_min", "48", "-sc_threshold", "0",
                    "-c:a", "aac", "-b:a", rendition["a_bitrate"], "-ac", "2",
                    # hls_time 2 (no 4): segmentos más chicos -> arranca a
                    # reproducir más rápido (no espera a bajar un pedazo tan
                    # grande antes del primer frame), a costa de un poco más
                    # de overhead por tener más archivos.
                    "-f", "hls", "-hls_time", "2", "-hls_playlist_type", "vod",
                    "-hls_flags", "independent_segments",
                    "-hls_segment_filename", os.path.join(out_dir, f"{rendition['name']}_%03d.ts"),
                    os.path.join(out_dir, f"{rendition['name']}.m3u8"),
                ],
                capture_output=True,
                timeout=600,
            )
            if result.returncode != 0:
                print(
                    f"[_generate_hls] ffmpeg falló para {rendition['name']} "
                    f"(source={source_path}): {result.stderr.decode(errors='replace')[-2000:]}"
                )
                return False

        master_lines = ["#EXTM3U"]
        for rendition in HLS_RENDITIONS:
            master_lines.append(f"#EXT-X-STREAM-INF:BANDWIDTH={rendition['bandwidth']}")
            master_lines.append(f"{rendition['name']}.m3u8")
        with open(os.path.join(out_dir, "master.m3u8"), "w") as f:
            f.write("\n".join(master_lines) + "\n")
        return True
    except Exception as exc:
        print(f"[_generate_hls] excepción para {source_path}: {exc!r}")
        return False


def _compress_single_video(source_path: str, output_path: str) -> bool:
    """Recodifica a un único MP4 bien comprimido, SIN trocear en HLS.

    Para reels (típicamente cortos, 15-40s): con HLS, saltar hacia atrás en
    la barra de progreso podía obligar a rebufferear el nuevo segmento —
    sin ningún indicador de carga en pantalla, se sentía como si el video
    se hubiera recargado entero. Con un solo archivo, una vez que termina
    de bajar completo (rápido, siendo corto), adelantar/atrasar es
    instantáneo siempre — cero pedidos de red de por medio.

    Usa REEL_RENDITION (más liviana que "high" de HLS_RENDITIONS, ver su
    comentario) y las mismas correcciones (HDR->SDR, dimensiones pares, fps
    constante)."""
    if not shutil.which("ffmpeg"):
        return False
    is_hdr = _is_hdr_source(source_path)
    rendition = REEL_RENDITION
    scale = f"scale='min({rendition['max_dim']},iw)':'min({rendition['max_dim']},ih)':force_original_aspect_ratio=decrease:force_divisible_by=2"
    if is_hdr:
        video_filter = (
            "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
            "tonemap=tonemap=hable:desat=0,"
            f"zscale=t=bt709:m=bt709:r=tv,format=yuv420p,{scale}"
        )
    else:
        video_filter = scale
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", source_path,
                "-vf", video_filter,
                "-pix_fmt", "yuv420p",
                "-fps_mode", "cfr",
                "-c:v", "libx264", "-preset", "medium",
                "-crf", rendition["crf"], "-maxrate", rendition["v_maxrate"], "-bufsize", rendition["v_bufsize"],
                "-c:a", "aac", "-b:a", rendition["a_bitrate"], "-ac", "2",
                "-movflags", "+faststart",
                output_path,
            ],
            capture_output=True,
            timeout=600,
        )
        if result.returncode != 0:
            print(
                f"[_compress_single_video] ffmpeg falló (source={source_path}): "
                f"{result.stderr.decode(errors='replace')[-2000:]}"
            )
            return False
        return os.path.getsize(output_path) > 0
    except Exception as exc:
        print(f"[_compress_single_video] excepción para {source_path}: {exc!r}")
        return False


def save_image(file: UploadFile, subfolder: str = "products") -> str:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Formato no permitido. Usa: {', '.join(ALLOWED_EXT)}")

    folder = os.path.join(settings.media_base_path, "marketplace", subfolder)
    os.makedirs(folder, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(folder, filename)

    # Igual que save_video: se escribe por chunks para poder cortar apenas
    # se supera el límite, en vez de leer el archivo completo a memoria
    # (antes no había ningún límite de tamaño para imágenes).
    size = 0
    with open(filepath, "wb") as f:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_IMAGE_SIZE_BYTES:
                f.close()
                os.remove(filepath)
                raise HTTPException(
                    status_code=400,
                    detail=f"La imagen supera el límite de {MAX_IMAGE_SIZE_BYTES // (1024*1024)} MB",
                )
            f.write(chunk)
    os.chmod(filepath, 0o644)

    return f"/media/marketplace/{subfolder}/{filename}"


def save_video(file: UploadFile, subfolder: str = "products") -> str:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_VIDEO_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Formato de video no permitido. Usa: {', '.join(ALLOWED_VIDEO_EXT)}",
        )

    folder = os.path.join(settings.media_base_path, "marketplace", subfolder, "videos")
    os.makedirs(folder, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(folder, filename)

    size = 0
    with open(filepath, "wb") as f:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_VIDEO_SIZE_BYTES:
                f.close()
                os.remove(filepath)
                raise HTTPException(
                    status_code=400,
                    detail=f"El video supera el límite de {MAX_VIDEO_SIZE_BYTES // (1024*1024)} MB",
                )
            f.write(chunk)
    # 644, no el 600 por defecto — nginx (en el compose local, y cualquier
    # reverse proxy que no corra como root) necesita poder LEER el archivo
    # para servirlo; sin esto tira 403 aunque el archivo exista y esté bien.
    os.chmod(filepath, 0o644)

    _remux_faststart(filepath)

    if subfolder == "reels":
        # Reels: un solo archivo bien comprimido, SIN HLS — son cortos, así
        # que una vez bajado completo el seek es instantáneo siempre (sin
        # pedidos de red a mitad de reproducción). Con HLS, saltar hacia
        # atrás podía rebufferear y sentirse como una recarga completa.
        name_without_ext = os.path.splitext(filename)[0]
        target_path = os.path.join(folder, f"{name_without_ext}.mp4")
        fd, tmp_path = tempfile.mkstemp(suffix=".mp4", dir=folder)
        os.close(fd)
        if _compress_single_video(filepath, tmp_path):
            os.replace(tmp_path, target_path)
            os.chmod(target_path, 0o644)
            if filepath != target_path:
                os.remove(filepath)
            return f"/media/marketplace/{subfolder}/videos/{name_without_ext}.mp4"
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        # Si falla la compresión (o no hay ffmpeg), se sirve el original tal
        # cual se subió — ya con faststart, aunque sin la recompresión.
        return f"/media/marketplace/{subfolder}/videos/{filename}"

    # Productos (tutoriales) — pueden ser más largos, ahí streaming
    # adaptativo (HLS) sigue teniendo sentido: si se genera bien, esa es la
    # URL que se devuelve (el reproductor la detecta sola). Si falla o no
    # hay ffmpeg, se cae al .mp4 de siempre.
    hls_dir = os.path.splitext(filepath)[0]
    os.makedirs(hls_dir, exist_ok=True)
    if _generate_hls(filepath, hls_dir):
        name_without_ext = os.path.splitext(filename)[0]
        return f"/media/marketplace/{subfolder}/videos/{name_without_ext}/master.m3u8"
    shutil.rmtree(hls_dir, ignore_errors=True)

    return f"/media/marketplace/{subfolder}/videos/{filename}"


def get_video_download_url(video_url: Optional[str]) -> Optional[str]:
    """Dado el video_url guardado (el master.m3u8 de un HLS, o un .mp4
    directo de antes de este cambio), devuelve la URL de un único archivo
    descargable — el .mp4 original que se guarda como respaldo aunque el
    reproductor use el HLS. Sirve para que el admin pueda "recuperar" el
    video tal como lo subieron, sin depender de los fragmentos del stream."""
    if not video_url:
        return None
    if not video_url.endswith("/master.m3u8"):
        return video_url

    hls_dir_url = video_url.rsplit("/", 1)[0]  # .../videos/{uuid}
    if not hls_dir_url.startswith("/media/"):
        return None
    relative_dir = hls_dir_url[len("/media/"):]  # marketplace/.../videos/{uuid}
    parent_relative = os.path.dirname(relative_dir)  # marketplace/.../videos
    uuid_name = os.path.basename(relative_dir)
    parent_fs = os.path.join(settings.media_base_path, parent_relative)
    if not os.path.isdir(parent_fs):
        return None

    for fname in os.listdir(parent_fs):
        stem, ext = os.path.splitext(fname)
        if stem == uuid_name and ext.lower() in ALLOWED_VIDEO_EXT:
            return f"/media/{parent_relative}/{fname}"
    return None
