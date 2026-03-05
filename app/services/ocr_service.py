"""
OCR Service — Extracción rápida de facturas sin IA generativa
Flujo: Cloud Vision (~1-2s) + regex → resultado en <3s vs 20s de Gemini
Fallback a Gemini solo cuando confidence < OCR_CONFIDENCE_THRESHOLD
"""
import re
import base64
import asyncio
import os
from typing import Dict, Optional
from app.utils.logger import setup_logger
from app.schemas.invoice_schema import InvoiceSchema
from config import settings

logger = setup_logger("ocr_service")

# ---------------------------------------------------------------------------
# Patrones regex para facturas peruanas (formato SUNAT)
# ---------------------------------------------------------------------------

# RUC: exactamente 11 dígitos, empieza con 10 (persona natural) o 20 (empresa)
RUC_PATTERN = re.compile(r'\b((?:10|20)\d{9})\b')

# Número de factura/boleta SUNAT: F/B/E + 3 dígitos + guión + 7-8 dígitos
# Ej: F001-00001234, B001-1234567, E001-00000001
INVOICE_NUM_PATTERN = re.compile(
    r'\b([FBEfbe]\d{3}-\d{6,8})\b|'           # Formato corto
    r'\b(FACTURA[:\s]+[FBEfbe]\d{3}-\d+)\b|'  # Con prefijo "FACTURA"
    r'\b(N[°º.]\s*[FBEfbe]\d{3}-\d+)\b',      # Con "N°"
    re.IGNORECASE
)

# Fecha: DD/MM/YYYY o YYYY-MM-DD o DD-MM-YYYY
DATE_PATTERN = re.compile(
    r'\b(\d{2})[/\-](\d{2})[/\-](\d{4})\b|'  # DD/MM/YYYY o DD-MM-YYYY
    r'\b(\d{4})[/\-](\d{2})[/\-](\d{2})\b'   # YYYY-MM-DD
)

# Montos: número con separador de miles opcional y decimales
AMOUNT_PATTERN = re.compile(r'\b\d{1,3}(?:[,\.]\d{3})*(?:[,\.]\d{2})?\b')

# Total: línea que contenga "TOTAL" seguida de un monto.
# Acepta: "TOTAL:", "TOTAL A PAGAR:", "TOTAL VENTA:", sin espacios extra.
TOTAL_PATTERN = re.compile(
    r'(?:IMPORTE\s+)?TOTAL\s*(?:A\s+PAGAR|VENTA|FACTURA|NETO|GENERAL|S/\.?)?\s*[:\s]+\s*([0-9][0-9,\.]+)',
    re.IGNORECASE
)

# IGV / Tax (18% en Perú) — acepta "IGV:", "I.G.V.:", "IGV 18%:"
IGV_PATTERN = re.compile(
    r'I\.?G\.?V\.?\s*(?:\(?18\s*%?\)?)?\s*[:\s]+\s*([0-9][0-9,\.]+)',
    re.IGNORECASE
)

# Subtotal (OP. GRAVADAS, SUBTOTAL, BASE IMPONIBLE)
SUBTOTAL_PATTERN = re.compile(
    r'(?:OP(?:ERACIONES)?\.?\s+GRAVADAS?|SUBTOTAL|BASE\s+IMPON[Ii]BLE|OP\.\s*GRAV\.?|VALOR\s+VENTA)\s*[:\s]+\s*([0-9][0-9,\.]+)',
    re.IGNORECASE
)

# Nombre del emisor: suele aparecer antes del RUC o después de "Razón Social"
SUPPLIER_PATTERN = re.compile(
    r'(?:RAZ[OÓ]N\s+SOCIAL|EMPRESA|EMISOR|PROVEEDOR)[:\s]+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ0-9\s\.\,\-&]+?)(?:\n|RUC|$)',
    re.IGNORECASE
)

# Cliente / receptor
CUSTOMER_PATTERN = re.compile(
    r'(?:CLIENTE|RECEPTOR|SE\u00d1OR\(ES\)|SR\.?|SRA\.?|ADQUIRIENTE)[:\s]+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ0-9\s\.\,\-&]+?)(?:\n|RUC|DNI|$)',
    re.IGNORECASE
)

# Moneda
CURRENCY_PATTERN = re.compile(r'\b(PEN|USD|EUR|SOLES?|D[OÓ]LARES?)\b', re.IGNORECASE)

# Unidades de medida comunes en facturas peruanas
UNIT_PATTERN = re.compile(
    r'\b(UND|UNID(?:AD(?:ES)?)?|KG|KGS|GR|MGR|LT|LTS|MT|MTS|M2|M3|'
    r'CAJA|CJAS?|PQTE|PQTES?|ROLLO|ROLLOS|JGO|JGS|SRV|SERV|HRS?|'
    r'GLN|GLNS?|TON|TNLDA|ZZ|NIU|KWH|PZA|PZS)\b',
    re.IGNORECASE
)

# Línea de ítem: número de ítem + descripción + cantidad + precio unitario + total
# Formato típico SUNAT: N°  CÓDIGO/DESC  UNIDAD  CANT  P.UNIT  IMPORTE
# Capturas dos variantes:
#   Completa:  1  Producto XYZ  UND  2.00  500.00  1,000.00
#   Sin código: 1  Descripción  2.00  500.00  1,000.00
ITEM_LINE_PATTERN = re.compile(
    r'^\s*(\d{1,3})\s+'                        # N° ítem (1-999)
    r'(.+?)\s+'                                 # descripción (lazy)
    r'(?:(' +                                   # unidad (opcional)
    r'UND|UNID(?:AD(?:ES)?)?|KG|KGS?|GR|MGR|LT|LTS?|MT|MTS?|M2|M3|'
    r'CAJA|CJAS?|PQTE|PQTES?|ROLLO|ROLLOS?|JGO|JGS|SRV|SERV|HRS?|'
    r'GLN|GLNS?|TON|TNLDA|ZZ|NIU|KWH|PZA|PZS'
    r')\s+)?'
    r'(\d[\d,\.]*)\s+'                          # cantidad
    r'(\d[\d,\.]*)\s+'                          # precio unitario
    r'(\d[\d,\.]+)',                             # importe/total
    re.IGNORECASE | re.MULTILINE
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_amount(raw: str) -> Optional[float]:
    """Convierte '1,234.56' o '1.234,56' a float."""
    if not raw:
        return None
    raw = raw.strip()
    # Detectar formato europeo (punto como miles, coma como decimal)
    if re.search(r'\d\.\d{3},', raw):
        raw = raw.replace('.', '').replace(',', '.')
    else:
        raw = raw.replace(',', '')
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_date(text: str) -> Optional[str]:
    """Extrae la primera fecha encontrada y la convierte a YYYY-MM-DD."""
    m = DATE_PATTERN.search(text)
    if not m:
        return None
    groups = m.groups()
    if groups[0]:  # DD/MM/YYYY
        return f"{groups[2]}-{groups[1]}-{groups[0]}"
    else:           # YYYY-MM-DD
        return f"{groups[3]}-{groups[4]}-{groups[5]}"


def _extract_first_group(pattern: re.Pattern, text: str) -> Optional[str]:
    m = pattern.search(text)
    if not m:
        return None
    # Retorna el primer grupo no vacío
    for g in m.groups():
        if g:
            return g.strip()
    return None


def _extract_items(text: str) -> list:
    """
    Extrae las líneas de detalle (ítems) de una factura SUNAT desde texto plano.

    Estrategia:
    1. Busca la sección de detalle delimitada por encabezados típicos
       (DESCRIPCIÓN, CANT, P.UNIT, IMPORTE, etc.).
    2. Aplica ITEM_LINE_PATTERN sobre esa sección.
    3. Si no encuentra nada con el patrón estricto, intenta un patrón
       alternativo relajado (descripción + 3 números al final de línea).
    """
    items = []

    # Aislar la sección de detalle: desde el encabezado de la tabla hasta el subtotal/total
    section_match = re.search(
        r'(?:DESCRIPCI[OÓ]N|DETALLE|CONCEPTO|BIEN\s+O\s+SERVICIO|PRODUCT[O]?)\b.{0,120}\n'
        r'([\s\S]+?)'
        r'(?:OP(?:ERACIONES)?\.?\s+GRAV|SUBTOTAL|BASE\s+IMPON|I\.?G\.?V|TOTAL)',
        text, re.IGNORECASE
    )
    section_text = section_match.group(1) if section_match else text

    # --- Intento 1: patrón estricto con N° ítem ---
    for m in ITEM_LINE_PATTERN.finditer(section_text):
        # grupos: (num, descripcion, unidad_opt, cantidad, precio_unit, importe)
        desc    = m.group(2).strip() if m.group(2) else None
        unit    = m.group(3).strip().upper() if m.group(3) else None
        qty     = _clean_amount(m.group(4))
        uprice  = _clean_amount(m.group(5))
        tprice  = _clean_amount(m.group(6))

        # Descartar líneas que parezcan encabezados o subtotales
        if desc and re.search(
            r'^(?:DESCRIPCI[OÓ]N|CANTIDAD|PRECIO|IMPORTE|SUBTOTAL|TOTAL|IGV|RUC)$',
            desc, re.IGNORECASE
        ):
            continue

        # Descartar si la cantidad parece un año (>1900)
        if qty and qty > 1900:
            continue

        if desc and (qty is not None or tprice is not None):
            items.append({
                "description": desc,
                "quantity":    qty,
                "unit_price":  uprice,
                "total_price": tprice,
                "unit":        unit,
            })

    if items:
        return items

    # --- Intento 2: patrón relajado sin N° de ítem ---
    # Captura líneas con descripción seguida de exactamente 2 o 3 montos al final
    relaxed = re.compile(
        r'^([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ0-9\s\-\/\.\,\(\)]{3,60}?)\s+'
        r'(?:(' + r'UND|UNID|KG|KGS?|GR|LT|LTS?|MT|MTS?|M2|M3|CAJA|SRV|SERV|HRS?|NIU|ZZ' + r')\s+)?'
        r'(\d[\d,\.]*)\s+'
        r'(\d[\d,\.]*)\s+'
        r'(\d[\d,\.]+)\s*$',
        re.IGNORECASE | re.MULTILINE
    )
    for m in relaxed.finditer(section_text):
        desc   = m.group(1).strip()
        unit   = m.group(2).strip().upper() if m.group(2) else None
        qty    = _clean_amount(m.group(3))
        uprice = _clean_amount(m.group(4))
        tprice = _clean_amount(m.group(5))

        if desc and re.search(
            r'^(?:DESCRIPCI[OÓ]N|CANTIDAD|PRECIO|IMPORTE|SUBTOTAL|TOTAL|IGV)$',
            desc, re.IGNORECASE
        ):
            continue
        if qty and qty > 1900:
            continue

        if desc and (qty is not None or tprice is not None):
            items.append({
                "description": desc,
                "quantity":    qty,
                "unit_price":  uprice,
                "total_price": tprice,
                "unit":        unit,
            })

    return items


def _calculate_confidence(data: dict) -> float:
    """
    Calcula qué tan completa es la extracción (0.0 a 1.0).
    Campos críticos tienen más peso.
    """
    weights = {
        "invoice_number": 0.25,
        "supplier_ruc": 0.25,
        "total": 0.20,
        "invoice_date": 0.15,
        "supplier_name": 0.10,
        "tax": 0.05,
    }
    score = 0.0
    for field, weight in weights.items():
        if data.get(field) is not None:
            score += weight
    return round(score, 2)


# ---------------------------------------------------------------------------
# Extracción de campos desde texto plano (regex, sin IA)
# ---------------------------------------------------------------------------

def extract_invoice_from_text(text: str, filename: str, sequence_id: int) -> Dict:
    """
    Extrae campos de factura usando regex puro sobre texto ya extraído.
    Instantáneo (0ms de latencia de red). Ideal para PDFs digitales SUNAT.
    """
    logger.log_file_processing(
        filename=filename,
        sequence_id=sequence_id,
        file_type="text",
        status="ocr_regex_extraction_started"
    )

    # Normalizar texto
    text_upper = text.upper()

    # Extraer número de factura
    inv_match = INVOICE_NUM_PATTERN.search(text)
    invoice_number = None
    if inv_match:
        for g in inv_match.groups():
            if g:
                invoice_number = g.strip().upper()
                break

    # RUC del emisor vs cliente
    # Heurística: en facturas SUNAT el emisor está en el HEADER (antes de la
    # sección 'CLIENTE:/RECEPTOR:'); el cliente aparece después de esa etiqueta.
    ruc_matches = RUC_PATTERN.findall(text)
    supplier_ruc = None
    customer_ruc = None

    if ruc_matches:
        client_section_match = re.search(
            r'(?:CLIENTE|RECEPTOR|SE[ÑN]OR(?:ES)?|ADQUIRIENTE|DESTINATARIO)[:\s]',
            text, re.IGNORECASE
        )
        if client_section_match:
            header_text = text[:client_section_match.start()]
            client_text  = text[client_section_match.start():]
            header_rucs = RUC_PATTERN.findall(header_text)
            client_rucs = RUC_PATTERN.findall(client_text)
            # El RUC del header (zona logo/encabezado) = emisor
            supplier_ruc = header_rucs[0] if header_rucs else ruc_matches[0]
            customer_ruc = client_rucs[0] if client_rucs else (ruc_matches[1] if len(ruc_matches) > 1 else None)
        else:
            # Sin separador claro: primer RUC = emisor, segundo = cliente
            supplier_ruc = ruc_matches[0]
            customer_ruc = ruc_matches[1] if len(ruc_matches) > 1 else None

    # Fecha
    invoice_date = _parse_date(text)

    # Montos
    total_match = TOTAL_PATTERN.search(text)
    total = _clean_amount(total_match.group(1)) if total_match else None

    igv_match = IGV_PATTERN.search(text)
    tax = _clean_amount(igv_match.group(1)) if igv_match else None

    subtotal_match = SUBTOTAL_PATTERN.search(text)
    subtotal = _clean_amount(subtotal_match.group(1)) if subtotal_match else None

    # Si falta subtotal pero tenemos total e IGV, calcular
    if subtotal is None and total is not None and tax is not None:
        subtotal = round(total - tax, 2)

    # Si falta IGV pero tenemos total y subtotal, calcular (18% peruano)
    if tax is None and subtotal is not None:
        tax = round(subtotal * 0.18, 2)

    # Nombres
    supplier_name = _extract_first_group(SUPPLIER_PATTERN, text)
    customer_name = _extract_first_group(CUSTOMER_PATTERN, text)

    # Moneda
    cur_match = CURRENCY_PATTERN.search(text)
    currency = "PEN"  # Default Perú
    if cur_match:
        raw_cur = cur_match.group(1).upper()
        if "USD" in raw_cur or "DOLAR" in raw_cur:
            currency = "USD"
        elif "EUR" in raw_cur:
            currency = "EUR"

    invoice_data = {
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "supplier_name": supplier_name,
        "supplier_ruc": supplier_ruc,
        "customer_name": customer_name,
        "customer_ruc": customer_ruc,
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
        "currency": currency,
        "items": _extract_items(text),
        "source_file": filename,
        "sequence_id": sequence_id,
        "confidence_score": 0.0,
    }

    invoice_data["confidence_score"] = _calculate_confidence(invoice_data)

    # Normalizar a través de InvoiceSchema para garantizar la misma
    # estructura que retorna el path de Gemini (tipos validados, sin campos extra).
    try:
        validated = InvoiceSchema(**invoice_data).dict()
    except Exception:
        validated = invoice_data  # fallback si la validación falla

    logger.log_extraction_result(
        filename=filename,
        sequence_id=sequence_id,
        confidence_score=validated.get("confidence_score", 0.0),
        success=True,
        invoice_number=invoice_number,
        total=total
    )

    return {
        "success": True,
        "invoice_data": validated,
        "raw_response": text[:500],
        "extraction_method": "ocr_regex",
    }


# ---------------------------------------------------------------------------
# Cloud Vision OCR para imágenes y PDFs escaneados
# ---------------------------------------------------------------------------

class OCRService:
    """
    Extracción rápida usando Google Cloud Vision API.
    ~1-2s por imagen vs ~20s de Gemini Vision.
    Costo: $1.50/1000 imágenes vs ~$0.10-0.30/1000 tokens de Gemini.
    """

    def __init__(self):
        self._client = None
        self._available = False
        self._init_attempted = False

    def _get_client(self):
        """Lazy init del cliente de Cloud Vision usando las mismas credenciales que Gemini."""
        if self._init_attempted:
            return self._client
        self._init_attempted = True
        try:
            from google.cloud import vision  # type: ignore
            from google.oauth2.service_account import Credentials

            # Usar el mismo service account que Gemini/Vertex AI
            sa_path = (
                os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                or settings.google_application_credentials
            )

            if sa_path and os.path.exists(sa_path):
                credentials = Credentials.from_service_account_file(
                    sa_path,
                    scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
                self._client = vision.ImageAnnotatorClient(credentials=credentials)
                logger.log_info(
                    "⚡ Google Cloud Vision client initialized (service account)",
                    sa_path=sa_path
                )
            else:
                # Fallback: ADC (funciona en Cloud Run automáticamente)
                self._client = vision.ImageAnnotatorClient()
                logger.log_info("⚡ Google Cloud Vision client initialized (ADC)")

            self._available = True
        except ImportError:
            logger.log_warning(
                "google-cloud-vision not installed. Run: poetry add google-cloud-vision"
            )
        except Exception as e:
            logger.log_error("Failed to initialize Cloud Vision client", error=str(e))
        return self._client

    @property
    def available(self) -> bool:
        self._get_client()
        return self._available

    async def extract_text_from_image(self, image_base64: str) -> Optional[str]:
        """
        Envía imagen a Cloud Vision y retorna texto crudo.
        Se ejecuta en thread pool para no bloquear el event loop.
        """
        client = self._get_client()
        if not client:
            return None

        def _sync_ocr():
            from google.cloud import vision  # type: ignore
            image_bytes = base64.b64decode(image_base64)
            image = vision.Image(content=image_bytes)
            # DOCUMENT_TEXT_DETECTION optimizado para documentos con layout estructurado
            response = client.document_text_detection(image=image)
            if response.error.message:
                raise Exception(f"Vision API error: {response.error.message}")
            annotation = response.full_text_annotation
            return annotation.text if annotation else ""

        try:
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(None, _sync_ocr)
            return text
        except Exception as e:
            logger.log_error("Cloud Vision OCR failed", error=str(e))
            return None

    async def extract_invoice_from_image(
        self, image_base64: str, filename: str, sequence_id: int
    ) -> Dict:
        """
        Pipeline completo: OCR → regex → resultado.
        Si el cliente no está disponible devuelve needs_gemini=True.
        """
        if not self.available:
            return {"success": False, "needs_gemini": True, "error": "OCR not available"}

        logger.log_file_processing(
            filename=filename,
            sequence_id=sequence_id,
            file_type="image",
            status="ocr_vision_started"
        )

        raw_text = await self.extract_text_from_image(image_base64)
        if not raw_text or len(raw_text.strip()) < 20:
            logger.log_warning(
                "Cloud Vision returned insufficient text",
                filename=filename,
                chars=len(raw_text) if raw_text else 0
            )
            return {"success": False, "needs_gemini": True, "error": "Insufficient OCR text"}

        result = extract_invoice_from_text(raw_text, filename, sequence_id)
        result["extraction_method"] = "cloud_vision_ocr"
        return result


# Singleton global
ocr_service = OCRService()
