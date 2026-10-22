import os
import shutil
import subprocess
import tempfile
import uuid
from typing import Optional, Set, Tuple

from fastapi import HTTPException, UploadFile

from app.core import storage

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
# "mantené esta calidad visual" y usa los bits que haga falta.
#
# v_maxrate/v_bufsize son el techo de los PICOS, no solo del promedio. Con
# bufsize mayor que maxrate (antes: high 4000k/6000k), x264 puede volcar el
# buffer entero en un segmento: medido en producción, cada 4 segmentos de 2s
# "high" llegaba a ~7 Mbps aunque el promedio fuera ~3.9. Con CloudFront
# (que entrega lo bastante rápido como para que el reproductor elija "high")
# esos picos vaciaban el buffer y el video se cortaba cada ~8 segundos.
# bufsize = maxrate mantiene los picos cerca del techo declarado.
HLS_RENDITIONS = [
    {"name": "low", "max_dim": 720, "crf": "23", "v_maxrate": "1200k", "v_bufsize": "1200k", "a_bitrate": "128k"},
    {"name": "high", "max_dim": 1920, "crf": "20", "v_maxrate": "3000k", "v_bufsize": "3000k", "a_bitrate": "128k"},
]

# Segmentos más cortos que esto (el último de cada video, típicamente) no
# cuentan para el pico: unos pocos KB en una fracción de segundo darían un
# "bitrate" inflado que no representa la reproducción real.
_MIN_SEGMENT_SECONDS_FOR_PEAK = 1.0


def _measure_rendition_bitrates(playlist_path: str) -> Tuple[int, int]:
    """(pico, promedio) en bits/s de una variante HLS ya generada, medidos
    sobre los segmentos reales. El pico va como BANDWIDTH en el master: es lo
    que el reproductor usa para decidir si le alcanza la conexión, y antes se
    declaraba un valor fijo (4.3 Mbps para "high") muy por debajo del pico
    real, así que elegía "high" sin poder sostenerla."""
    out_dir = os.path.dirname(playlist_path)
    peak = 0
    total_bits = 0
    total_seconds = 0.0
    duration = None
    with open(playlist_path) as f:
        for raw in f:
            line = raw.strip()
            if line.startswith("#EXTINF:"):
                duration = float(line[len("#EXTINF:"):].split(",")[0])
            elif line and not line.startswith("#") and duration:
                bits = os.path.getsize(os.path.join(out_dir, line)) * 8
                total_bits += bits
                total_seconds += duration
                if duration >= _MIN_SEGMENT_SECONDS_FOR_PEAK:
                    peak = max(peak, int(bits / duration))
                duration = None
    average = int(total_bits / total_seconds) if total_seconds else 0
    return (peak or average), average

# Calidad del MP4 único de los REELS (ver save_video). Los reels volvieron
# de HLS a un solo MP4 porque HLS necesita 3 pedidos seguidos antes del
# primer frame (master -> playlist -> segmento), y con ~0.4-0.6 s de latencia
# por pedido hacia CloudFront eso solo ya eran ~1.5 s de arranque. Un MP4
# con faststart arranca con UN pedido, y la app puede bajar a disco el
# comienzo de varios reels siguientes (cosa que con HLS no se podía).
#
# Historial de ajustes probados en esta VPS/conexión, de más liviano a más
# pesado:
#   1080p/CRF24/1800kbps -> cargaba fluido pero tardaba demasiado en
#     bufferear en datos móviles ("a tirones" mientras carga).
#   640px/CRF27/700kbps  -> carga fluida, pero se ve pixelado/con poca
#     nitidez (resolución y bits por pixel ambos muy bajos).
#   720px/CRF25/1100kbps -> confirmado en el celular real, fluido y buena
#     calidad.
#   720px/CRF23/1400kbps -> también confirmado fluido sin cortes.
#   900px/CRF21/1800kbps -> volvió a laguear, ese salto fue demasiado grande.
# OJO: en ese historial "720px" era el lado LARGO (max_dim): un reel vertical
# de 1080x1920 salía en 406x720, casi 360p, y por eso se veía borroso en el
# celular aunque fluyera bien.
#
# Ahora el tope va sobre el lado CORTO (short_side): 720 real, o sea
# 720x1280 en vertical. Medido sobre reels reales contra el original: 76 %
# más peso (~1.6 Mbps) y 35 % menos distorsión (SSIM 0.971 -> 0.981) que el
# 406x720. Sigue muy por debajo de los ~3-4 Mbps de la "high" de HLS que se
# cortaba con wifi.
#   - CRF 23 + preset "slow": mejor compresión con el mismo peso, a costa de
#     algo más de tiempo de procesamiento en el VPS.
#   - maxrate 2000k / bufsize 1.5 × maxrate: margen para escenas con
#     movimiento sin picos como los que cortaban la "high" de HLS.
#   - tope de 30 fps (max_fps): un video de 60 fps reparte los bits entre el
#     doble de cuadros; a 30 cada cuadro sale más nítido.
REEL_RENDITION = {"short_side": 720, "crf": "23", "v_maxrate": "2000k", "v_bufsize": "3000k", "a_bitrate": "112k", "preset": "slow", "max_fps": "30"}

# Nombre del MP4 procesado dentro de la carpeta del reel:
# .../videos/{uuid}/video.mp4 (mismo esquema de carpeta que el HLS, así
# borrar/limpiar/descargar el original funcionan igual para los dos).
REEL_MP4_NAME = "video.mp4"
_PROCESSED_NAMES = ("master.m3u8", REEL_MP4_NAME)


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
            playlist = f"{rendition['name']}.m3u8"
            peak, average = _measure_rendition_bitrates(os.path.join(out_dir, playlist))
            master_lines.append(
                f"#EXT-X-STREAM-INF:BANDWIDTH={peak},AVERAGE-BANDWIDTH={average}"
            )
            master_lines.append(playlist)
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
    # El lado CORTO a short_side (sin agrandar videos más chicos) y el largo
    # proporcional; -2 = par, como exige libx264. Vertical 1080x1920 ->
    # 720x1280; horizontal 1920x1080 -> 1280x720.
    side = rendition["short_side"]
    scale = (
        f"scale='if(gt(ih,iw),min({side},iw),-2)':'if(gt(ih,iw),-2,min({side},ih))'"
    )
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
                # Tope, no valor fijo: un video de 24/25/30 fps queda igual;
                # solo baja los de más (60 fps) a max_fps.
                "-fpsmax", rendition["max_fps"],
                "-c:v", "libx264", "-preset", rendition["preset"],
                "-crf", rendition["crf"], "-maxrate", rendition["v_maxrate"], "-bufsize", rendition["v_bufsize"],
                # Keyframe cada 60 frames (2 s a 30 fps): adelantar/atrasar en
                # la barra cae siempre cerca de un keyframe, sin decodificar de más.
                "-g", "60", "-keyint_min", "60",
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


def _write_upload(file: UploadFile, dest_path: str, max_bytes: int, label: str) -> None:
    """Escribe el upload por chunks y corta apenas se supera el límite, en
    vez de leer el archivo completo a memoria."""
    size = 0
    with open(dest_path, "wb") as f:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                raise HTTPException(
                    status_code=400,
                    detail=f"{label} supera el límite de {max_bytes // (1024*1024)} MB",
                )
            f.write(chunk)


def save_image(file: UploadFile, subfolder: str = "products") -> str:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Formato no permitido. Usa: {', '.join(ALLOWED_EXT)}")

    filename = f"{uuid.uuid4().hex}{ext}"
    key = f"marketplace/{subfolder}/{filename}"
    with tempfile.TemporaryDirectory() as work:
        local_path = os.path.join(work, filename)
        _write_upload(file, local_path, MAX_IMAGE_SIZE_BYTES, "La imagen")
        storage.put_file(local_path, key)
    return storage.public_url(key)


def save_video(file: UploadFile, subfolder: str = "products") -> str:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_VIDEO_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Formato de video no permitido. Usa: {', '.join(ALLOWED_VIDEO_EXT)}",
        )

    name = uuid.uuid4().hex
    filename = f"{name}{ext}"
    videos_key = f"marketplace/{subfolder}/videos"

    # ffmpeg necesita archivos locales: se procesa todo en una carpeta
    # temporal y recién al final se manda al storage (disco o MinIO).
    with tempfile.TemporaryDirectory() as work:
        filepath = os.path.join(work, filename)
        _write_upload(file, filepath, MAX_VIDEO_SIZE_BYTES, "El video")
        _remux_faststart(filepath)

        # Reels: un solo MP4 720p con faststart (ver REEL_RENDITION).
        # Productos: streaming adaptativo (HLS), el reproductor pide de a
        # segmentos y sube/baja de calidad según la velocidad real.
        # En los dos casos el original se guarda igual, como respaldo
        # descargable.
        out_dir = os.path.join(work, name)
        os.makedirs(out_dir)
        if subfolder == "reels":
            processed = REEL_MP4_NAME
            ok = _compress_single_video(filepath, os.path.join(out_dir, processed))
        else:
            processed = "master.m3u8"
            ok = _generate_hls(filepath, out_dir)
        if ok:
            storage.put_dir(out_dir, f"{videos_key}/{name}", last=processed)
        storage.put_file(filepath, f"{videos_key}/{filename}")

    if ok:
        return storage.public_url(f"{videos_key}/{name}/{processed}")
    return storage.public_url(f"{videos_key}/{filename}")


def _processed_dir_key(key: str) -> Optional[str]:
    """Carpeta .../videos/{uuid} si la clave es un video procesado (master.m3u8
    de HLS o video.mp4 de reel), si no None."""
    folder, _, name = key.rpartition("/")
    return folder if folder and name in _PROCESSED_NAMES else None


def _url_to_key(url: str) -> Optional[str]:
    """Convierte una URL guardada en base de datos a su clave de storage
    (relativa, ej. "marketplace/reels/videos/abc/master.m3u8"), sea cual sea
    el backend que la sirve. `None` si la URL no es nuestra (ej. un link
    externo que el admin pegó a mano) — esas nunca se tocan.

    Dos formas posibles, según el backend que tenía activo cuando se guardó:
      - "/media/<clave>"                      (disco o MinIO, vía /media/)
      - "<base pública de AWS>/<clave>"        (reels en S3, URL absoluta)
    """
    if url.startswith("/media/"):
        return url[len("/media/"):]
    from app.config.settings import settings

    if settings.aws_bucket:
        aws_prefix = storage.aws_base_url() + "/"
        if url.startswith(aws_prefix):
            return url[len(aws_prefix):]
    return None


def get_video_download_url(video_url: Optional[str]) -> Optional[str]:
    """Dado el video_url guardado (el master.m3u8 de un HLS, el video.mp4
    procesado de un reel, o un .mp4 directo viejo), devuelve la URL del
    original que se guarda como respaldo, para que el admin pueda descargar
    el video tal como lo subieron."""
    if not video_url:
        return None
    key = _url_to_key(video_url)
    hls_dir_key = _processed_dir_key(key) if key else None  # .../videos/{uuid}
    if hls_dir_key is None:
        return video_url
    # El original vive al lado de la carpeta HLS: .../videos/{uuid}.<ext>
    for key in storage.list_keys(hls_dir_key + "."):
        if os.path.splitext(key)[1].lower() in ALLOWED_VIDEO_EXT:
            return storage.public_url(key)
    return None


def is_managed_media(url: Optional[str]) -> bool:
    """True solo para archivos que subió este backend. Links externos o
    rutas de otro backend (ej. productos importados del salón) no se tocan."""
    return bool(url) and _url_to_key(url) is not None


def media_storage_keys(url: str) -> Tuple[Set[str], Set[str]]:
    """(claves exactas, prefijos) que ocupa en el storage un archivo publicado.
    Un video procesado (HLS o MP4 de reel) es su carpeta más el original de
    respaldo."""
    key = _url_to_key(url)
    if key is None:
        return set(), set()
    hls_dir = _processed_dir_key(key)
    if hls_dir is not None:
        return set(), {hls_dir + "/", hls_dir + "."}
    return {key}, set()


def delete_media(*urls: str) -> None:
    """Borra del storage los archivos de cada URL. Si algo falla solo se
    registra: el registro ya se guardó y un archivo huérfano no rompe nada
    (lo levanta después el comando de limpieza)."""
    for url in urls:
        if not is_managed_media(url):
            continue
        try:
            keys, prefixes = media_storage_keys(url)
            for key in keys:
                storage.delete_key(key)
            for prefix in prefixes:
                if prefix.endswith("/"):
                    storage.delete_prefix(prefix)
                else:
                    for key in storage.list_keys(prefix):
                        storage.delete_key(key)
        except Exception as exc:
            print(f"[delete_media] no se pudo borrar {url}: {exc!r}")
