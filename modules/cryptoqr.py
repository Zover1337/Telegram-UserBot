__MODULE__ = "CryptoQR ▣"
__HELP__ = "<code>.cqr &lt;текст или ссылка&gt;</code> — Создать QR-код локально"

import asyncio
import html
from io import BytesIO

from pyrogram import Client, filters
from pyrogram.types import Message

from utils import ONLY_ME, PREFIXES

MAX_QR_BYTES = 1200


def build_qr_image(value: str) -> BytesIO:
    if len(value.encode("utf-8")) > MAX_QR_BYTES:
        raise ValueError("QR payload exceeds supported capacity")

    import qrcode
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.colormasks import SolidFillColorMask
    from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer

    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=12,
        border=4,
    )
    qr.add_data(value)
    qr.make(fit=True)
    image = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=SolidFillColorMask(
            front_color=(39, 103, 246),
            back_color=(255, 255, 255),
        ),
    )

    output = BytesIO()
    output.name = "qrcode.png"
    image.save(output, format="PNG")
    output.seek(0)
    return output


@Client.on_message(filters.command("cqr", prefixes=PREFIXES) & ONLY_ME)
async def crypto_qr_handler(client: Client, msg: Message):
    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip():
        await msg.edit("Укажите текст или ссылку: <code>.cqr example.com</code>")
        return

    value = parts[1].strip()
    if len(value.encode("utf-8")) > MAX_QR_BYTES:
        await msg.edit("Текст слишком длинный. Максимум: 1200 байт в UTF-8.")
        return

    await msg.edit("Создаю QR-код...")
    try:
        image = await asyncio.to_thread(build_qr_image, value)
        await client.send_document(
            msg.chat.id,
            image,
            caption=f"<b>Содержимое:</b> <code>{html.escape(value[:600])}</code>",
            message_thread_id=msg.message_thread_id,
        )
    except Exception:
        await msg.edit("Не удалось создать QR-код.")
        return
    finally:
        if "image" in locals():
            image.close()

    await msg.delete()
