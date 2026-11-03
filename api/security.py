import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from pipeline.config import API_KEY

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str | None = Security(_api_key_header)) -> None:
    """Exige la cabecera X-API-Key. Sin API_KEY configurada, la API no atiende a nadie."""
    if not API_KEY:
        raise HTTPException(status_code=503, detail="API_KEY no está configurada en el servidor")
    # compare_digest compara en tiempo constante para no filtrar la clave por tiempos de respuesta.
    if not key or not secrets.compare_digest(key, API_KEY):
        raise HTTPException(status_code=401, detail="API key inválida o ausente")
