from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from moviepy.editor import VideoFileClip, AudioFileClip
import requests
import os
from google.cloud import storage
import tempfile

app = FastAPI()
# Añadir endpoint de salud
@app.get("/")
async def health_check():
    return {"status": "healthy"}
# Configuración específica de tu Google Cloud Storage
BUCKET_NAME = "amkrbucket"
BASE_VIDEO_NAME = "Video Base ‐ Hecho con Clipchamp (1).mp4"
storage_client = storage.Client()

class VideoRequest(BaseModel):
    audio_url: str

def download_file(url: str) -> str:
    """Descarga un archivo desde una URL y retorna la ruta temporal"""
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    response = requests.get(url)
    temp_file.write(response.content)
    temp_file.close()
    return temp_file.name

def get_base_video():
    """Obtiene el video base desde Google Cloud Storage"""
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(BASE_VIDEO_NAME)
    temp_video = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    blob.download_to_filename(temp_video.name)
    return temp_video.name

@app.post("/combine-video-audio")
async def combine_video_audio(request: VideoRequest):
    try:
        # Descargar el audio
        audio_path = download_file(request.audio_url)
        # Obtener el video base
        video_path = get_base_video()
        
        # Cargar video y audio
        video = VideoFileClip(video_path)
        audio = AudioFileClip(audio_path)
        
        # Ajustar duración del video a la duración del audio
        final_video = video.subclip(0, audio.duration)
        
        # Combinar video con audio
        final_video = final_video.set_audio(audio)
        
        # Guardar resultado temporal
        output_path = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4').name
        final_video.write_videofile(output_path)
        
        # Subir a Google Cloud Storage
        bucket = storage_client.bucket(BUCKET_NAME)
        output_blob_name = f"output_video_{os.path.basename(output_path)}"
        blob = bucket.blob(output_blob_name)
        blob.upload_from_filename(output_path)
        
        # Establecer el archivo como públicamente accesible
        blob.make_public()
        
        # Limpiar archivos temporales
        os.unlink(audio_path)
        os.unlink(video_path)
        os.unlink(output_path)
        
        # Retornar URL del video procesado
        return {"video_url": blob.public_url}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
