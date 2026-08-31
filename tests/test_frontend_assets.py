from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "oldphonekiosk"


def test_frontend_registers_static_assets_not_sidebar_panel():
    source = (COMPONENT / "frontend.py").read_text()
    assert "panel_custom" not in source
    assert "async_register_panel" not in source
    assert "async_remove_panel" not in source
    assert "StaticPathConfig" in source
    assert "async_ensure_lovelace_resource" in source
    assert "oldphonekiosk-intercom-card.js?v=0.1.36" in source


def test_lovelace_intercom_card_asset_exists_and_is_registered():
    old_panel = COMPONENT / "www" / "oldphonekiosk-panel.js"
    card = COMPONENT / "www" / "oldphonekiosk-intercom-card.js"
    assert not old_panel.exists()
    content = card.read_text()
    assert "customElements.define(\"oldphonekiosk-intercom-card\"" in content
    assert "window.customCards" in content
    assert "navigator.mediaDevices.getUserMedia" in content
    assert "async _ensureLocalAudio()" in content
    assert "replaceTrack(track)" in content
    assert "oldphonekiosk/intercom/start" in content
    assert "track.enabled = this._talking" in content
    assert "pointerdown" in content
    assert "Mów" in content
    assert "Object.prototype.hasOwnProperty.call(attrs, \"video_url\")" in content
    assert "hasPanelVideoUrl ? attrs.video_url : attrs.entity_picture" in content
    assert "Kamera wystartuje po kliknięciu Zadzwoń" in content
