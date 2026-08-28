from fastapi import APIRouter, File, UploadFile, Form
from app.config import SKILLS_MAP

router = APIRouter(prefix="/api", tags=["resume"])

@router.post("/resume-extract")
async def resume_extract(file: UploadFile = File(None), text: str = Form(None)):
    content = ""
    if file:
        data = await file.read()
        try:
            from PyPDF2 import PdfReader
            import io
            reader = PdfReader(io.BytesIO(data))
            for page in reader.pages:
                content += (page.extract_text() or "") + "\n"
        except:
            try:
                content = data.decode("utf-8", errors="ignore")
            except:
                content = ""
    if text:
        content += "\n" + text
    content_lower = content.lower()
    extracted = []
    for canon, aliases in SKILLS_MAP.items():
        for a in aliases:
            if a.lower() in content_lower:
                extracted.append(canon)
                break
    extracted = list(set(extracted))
    return {"text_preview": content[:2000], "skills": extracted, "count": len(extracted)}
