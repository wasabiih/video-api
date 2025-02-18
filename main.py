from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
from moviepy.editor import VideoFileClip, AudioFileClip
import requests
import os
from google.cloud import storage
import tempfile
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Configuración específica de tu Google Cloud Storage
BUCKET_NAME = "amkrbucket"
BASE_VIDEO_NAME = "Video Base ‐ Hecho con Clipchamp (1).mp4"
storage_client = storage.Client()

class VideoRequest(BaseModel):
    audio_url: HttpUrl

def validate_audio_file(file_path: str) -> bool:
    """Valida que el archivo sea un audio válido"""
    try:
        audio = AudioFileClip(file_path)
        duration = audio.duration
        audio.close()
        return True
    except Exception as e:
        logger.error(f"Error validando audio: {str(e)}")
        return False

def download_file(url: str) -> str:
    """Descarga un archivo desde una URL y retorna la ruta temporal"""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Verificar si la respuesta es exitosa
        
        content_type = response.headers.get('content-type', '')
        if not content_type.startswith('audio/'):
            raise ValueError(f"El archivo no es un audio válido. Content-Type: {content_type}")

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                temp_file.write(chunk)
        temp_file.close()
        
        if not validate_audio_file(temp_file.name):
            os.unlink(temp_file.name)
            raise ValueError("El archivo descargado no es un audio válido")
            
        return temp_file.name
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Error descargando el audio: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error procesando el audio: {str(e)}")

def get_base_video():
    """Obtiene el video base desde Google Cloud Storage"""
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(BASE_VIDEO_NAME)
        temp_video = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        blob.download_to_filename(temp_video.name)
        return temp_video.name
    except Exception as e:
        logger.error(f"Error obteniendo video base: {str(e)}")
        raise HTTPException(status_code=500, detail="Error accediendo al video base")

@app.get("/")
async def health_check():
    return {"status": "healthy"}

@app.post("/combine-video-audio")
async def combine_video_audio(request: VideoRequest):
    try:
        # Registrar inicio del proceso
        logger.info(f"Iniciando procesamiento con audio: {request.audio_url}")
        
        # Descargar el audio
        audio_path = download_file(str(request.audio_url))
        logger.info("Audio descargado exitosamente")
        
        # Obtener el video base
        video_path = get_base_video()
        logger.info("Video base obtenido exitosamente")
        
        # Cargar video y audio
        video = VideoFileClip(video_path)
        audio = AudioFileClip(audio_path)
        logger.info(f"Duración del audio: {audio.duration}")
        
        # Ajustar duración del video
        final_video = video.subclip(0, audio.duration)
        logger.info("Video recortado según duración del audio")
        
        # Combinar video con audio
        final_video = final_video.set_audio(audio)
        
        # Guardar resultado temporal
        output_path = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4').name
        final_video.write_videofile(output_path, codec='libx264', audio_codec='aac')
        logger.info("Video combinado exitosamente")
        
        # Subir a Google Cloud Storage
        bucket = storage_client.bucket(BUCKET_NAME)
        output_blob_name = f"output_video_{os.path.basename(output_path)}"
        blob = bucket.blob(output_blob_name)
        blob.upload_from_filename(output_path)
        blob.make_public()
        logger.info("Video subido a Cloud Storage")
        
        # Limpiar archivos temporales
        os.unlink(audio_path)
        os.unlink(video_path)
        os.unlink(output_path)
        video.close()
        audio.close()
        
        # Retornar URL del video procesado
        return {"video_url": blob.public_url}
    
    except Exception as e:
        logger.error(f"Error en el proceso: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
