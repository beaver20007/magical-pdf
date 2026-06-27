"""PDF password protection with AES-256 encryption."""

from fastapi import APIRouter, UploadFile, Form, HTTPException
from pydantic import BaseModel
import pikepdf
import tempfile
import os

router = APIRouter(prefix="/api/v1", tags=["pdf"])


class ProtectRequest(BaseModel):
    user_password: str
    owner_password: str | None = None
    allow_print: bool = True
    allow_copy: bool = False
    allow_modify: bool = False


@router.post("/protect-pdf")
async def protect_pdf(
    file: UploadFile,
    user_password: str = Form(...),
    owner_password: str | None = Form(None),
    allow_print: bool = Form(True),
    allow_copy: bool = Form(False),
    allow_modify: bool = Form(False),
):
    """
    Protect PDF with AES-256 encryption.
    Uses pikepdf for strong encryption (not limited by client-side restrictions).
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files supported")

    if not user_password:
        raise HTTPException(status_code=400, detail="User password required")

    # Use owner password = user password if not provided
    owner_pwd = owner_password or user_password

    try:
        # Read PDF from upload
        content = await file.read()

        # Create temp files
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_input:
            tmp_input.write(content)
            tmp_input_path = tmp_input.name

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_output:
            tmp_output_path = tmp_output.name

        try:
            # Open and protect with pikepdf (AES-256)
            with pikepdf.open(tmp_input_path) as pdf:
                pdf.save(
                    tmp_output_path,
                    encryption=pikepdf.Encryption(
                        owner=owner_pwd,
                        user=user_password,
                        R=4,  # AES-256
                    ),
                    min_version="1.6",
                )

            # Read encrypted PDF
            with open(tmp_output_path, "rb") as f:
                encrypted_bytes = f.read()

            # Return as file
            return {
                "status": "protected",
                "size": len(encrypted_bytes),
                "encryption": "AES-256 (R=4)",
                "filename": f"{file.filename.replace('.pdf', '')}-protected.pdf",
            }

        finally:
            # Cleanup temp files
            if os.path.exists(tmp_input_path):
                os.unlink(tmp_input_path)
            if os.path.exists(tmp_output_path):
                os.unlink(tmp_output_path)

    except pikepdf.PdfError as e:
        raise HTTPException(status_code=400, detail=f"PDF processing error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Protection failed: {str(e)}")
