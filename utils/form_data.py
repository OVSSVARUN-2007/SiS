from urllib.parse import parse_qs


async def safe_form_to_dict(request):
    """
    Read form payload safely.
    Works even when python-multipart is not installed by falling back
    to parsing x-www-form-urlencoded bodies.
    """
    try:
        form = await request.form()
        return dict(form)
    except AssertionError:
        raw = (await request.body()).decode("utf-8", errors="ignore")
        parsed = parse_qs(raw, keep_blank_values=True)
        return {key: (values[0] if values else "") for key, values in parsed.items()}
