from django.templatetags.static import static


def test_estaticos_sin_manifest_no_fallan(db):
    import re

    # sin manifest sale sin hash; con uno de un collectstatic previo, con hash
    assert re.search(r"core/logo(\.[0-9a-f]{12})?\.svg$", static("core/logo.svg"))


def test_base_sin_pedidos_de_terceros_que_bloquean_el_render(client, db):
    html = client.get("/").content.decode()
    assert "fonts.googleapis.com" not in html and "unpkg.com" not in html
    assert 'rel="preload"' in html and "font-display: swap" in html and "size-adjust" in html
    import re

    assert re.search(r'<script defer src="/static/core/htmx\.min(\.[0-9a-f]{12})?\.js">', html)


def test_con_manifest_el_nombre_lleva_hash(settings, tmp_path):
    from core.storage import EstaticosConHash

    settings.DEBUG = False
    st = EstaticosConHash(location=str(tmp_path), base_url="/static/")
    st.hashed_files = {"core/logo.svg": "core/logo.0123abcd.svg"}
    assert st.url("core/logo.svg") == "/static/core/logo.0123abcd.svg"
