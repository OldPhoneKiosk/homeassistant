class OldPhoneKioskIntercomCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._status = "Gotowy";
    this._sessionId = null;
    this._pc = null;
    this._localStream = null;
    this._unsubscribe = null;
  }

  static getConfigElement() {
    return document.createElement("oldphonekiosk-intercom-card-editor");
  }

  static getStubConfig() {
    return { type: "custom:oldphonekiosk-intercom-card", entity: "binary_sensor.oldphonekiosk_online" };
  }

  setConfig(config) {
    if (!config.entity && !config.device_id) {
      throw new Error("Set entity (an OldPhoneKiosk entity) or device_id");
    }
    this._config = config;
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  disconnectedCallback() {
    this._hangup(false);
  }

  getCardSize() {
    return this._config.camera_entity ? 6 : 3;
  }

  _deviceId() {
    if (this._config.device_id) return this._config.device_id;
    const state = this._hass?.states?.[this._config.entity];
    return state?.attributes?.bridge_device_id || state?.attributes?.device_id || "";
  }

  _cameraEntity() {
    if (this._config.camera_entity) return this._config.camera_entity;
    const configured = this._config.entity;
    if (configured?.startsWith("camera.")) return configured;
    const deviceId = this._deviceId();
    if (!deviceId || !this._hass) return "";
    const candidates = Object.entries(this._hass.states)
      .filter(([entityId, state]) => entityId.startsWith("camera.") && state.attributes?.bridge_device_id === deviceId)
      .map(([entityId]) => entityId);
    return candidates[0] || "";
  }

  _deviceName() {
    const state = this._hass?.states?.[this._config.entity];
    return this._config.name || state?.attributes?.friendly_name?.replace(/ online$/i, "") || this._deviceId() || "OldPhoneKiosk";
  }

  _online() {
    const state = this._hass?.states?.[this._config.entity];
    if (!state) return true;
    if (state.entity_id?.startsWith("binary_sensor.")) return state.state === "on";
    return state.state !== "unavailable" && state.state !== "unknown";
  }

  async _call() {
    if (!this._hass) return;
    const deviceId = this._deviceId();
    if (!deviceId) {
      this._setError("Brak bridge_device_id w encji/kartcie");
      return;
    }
    try {
      this._status = "Proszę o mikrofon…";
      this.render();
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("Przeglądarka nie udostępnia mikrofonu dla tej strony. Użyj HTTPS albo zaufanego adresu HA.");
      }
      this._localStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        video: false,
      });
      this._pc = new RTCPeerConnection({ iceServers: this._config.ice_servers || [] });
      for (const track of this._localStream.getAudioTracks()) {
        this._pc.addTrack(track, this._localStream);
      }
      this._pc.addTransceiver("audio", { direction: "sendrecv" });
      this._pc.ontrack = (event) => {
        const audio = this.shadowRoot.getElementById("remote-audio");
        if (audio && event.streams[0]) {
          audio.srcObject = event.streams[0];
          audio.play().catch(() => {});
        }
      };
      this._pc.oniceconnectionstatechange = () => {
        if (!this._pc) return;
        this._status = `Audio: ${this._pc.iceConnectionState}`;
        this.render();
      };
      this._pc.onicecandidate = (event) => {
        if (!event.candidate || !this._sessionId) return;
        this._hass.callWS({
          type: "oldphonekiosk/intercom/ice_candidate",
          session_id: this._sessionId,
          candidate: event.candidate.toJSON(),
        }).catch((err) => this._setError(err));
      };
      const start = await this._hass.callWS({
        type: "oldphonekiosk/intercom/start",
        device_id: deviceId,
      });
      this._sessionId = start.session_id;
      this._unsubscribe = await this._hass.connection.subscribeMessage(
        (event) => this._handleSignal(event),
        { type: "oldphonekiosk/intercom/subscribe", session_id: this._sessionId },
      );
      const offer = await this._pc.createOffer({ offerToReceiveAudio: true });
      await this._pc.setLocalDescription(offer);
      await this._hass.callWS({
        type: "oldphonekiosk/intercom/offer",
        session_id: this._sessionId,
        sdp: offer.sdp,
      });
      this._status = "Łączenie audio…";
      this.render();
    } catch (err) {
      this._setError(err);
      await this._hangup(false);
    }
  }

  async _handleSignal(frame) {
    if (!this._pc || frame.session_id !== this._sessionId) return;
    if (frame.action === "answer" && frame.sdp) {
      await this._pc.setRemoteDescription({ type: "answer", sdp: frame.sdp });
      this._status = "Rozmowa aktywna";
      this.render();
      return;
    }
    if (frame.action === "ice_candidate" && frame.candidate) {
      await this._pc.addIceCandidate(frame.candidate);
      return;
    }
    if (frame.action === "hangup") {
      await this._hangup(false);
      return;
    }
    if (frame.action === "error") {
      this._setError(frame.error || "Błąd interkomu");
      await this._hangup(false);
    }
  }

  async _hangup(send = true) {
    const sessionId = this._sessionId;
    this._sessionId = null;
    if (this._unsubscribe) {
      this._unsubscribe();
      this._unsubscribe = null;
    }
    if (this._pc) {
      this._pc.close();
      this._pc = null;
    }
    if (this._localStream) {
      for (const track of this._localStream.getTracks()) track.stop();
      this._localStream = null;
    }
    if (send && sessionId && this._hass) {
      await this._hass.callWS({ type: "oldphonekiosk/intercom/hangup", session_id: sessionId }).catch(() => {});
    }
    this._status = "Rozłączono";
    this.render();
  }

  _setError(err) {
    this._status = `Błąd: ${err?.message || err}`;
    this.render();
  }

  _cameraMarkup(cameraEntity) {
    if (!cameraEntity || !this._hass?.states?.[cameraEntity]) return "";
    const camera = this._hass.states[cameraEntity];
    const picture = camera.attributes?.entity_picture;
    if (!picture) return `<div class="camera-placeholder">${cameraEntity}</div>`;
    return `<img class="camera" src="${picture}" alt="${camera.attributes?.friendly_name || cameraEntity}" />`;
  }

  render() {
    if (!this.shadowRoot) return;
    const deviceId = this._deviceId();
    const cameraEntity = this._cameraEntity();
    const inCall = Boolean(this._sessionId);
    const online = this._online();
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { overflow: hidden; }
        .camera-wrap { background: #000; min-height: 160px; display: flex; align-items: center; justify-content: center; }
        .camera { display: block; width: 100%; height: auto; max-height: 420px; object-fit: contain; background: #000; }
        .camera-placeholder { color: var(--secondary-text-color); padding: 32px; text-align: center; }
        .body { padding: 16px; }
        .title { font-size: 18px; font-weight: 600; margin-bottom: 4px; }
        .subtitle { color: var(--secondary-text-color); font-size: 13px; margin-bottom: 12px; }
        .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
        button { cursor: pointer; border: 0; border-radius: 10px; padding: 10px 14px; font-weight: 600; }
        button.call { background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #fff); }
        button.hangup { background: var(--error-color, #db4437); color: #fff; }
        button:disabled { opacity: .45; cursor: not-allowed; }
        .status { margin-top: 12px; font-size: 13px; color: var(--secondary-text-color); }
        .pill { display: inline-block; border-radius: 999px; padding: 2px 8px; font-size: 12px; background: ${online ? "rgba(46, 125, 50, .14)" : "rgba(211, 47, 47, .14)"}; color: ${online ? "#2e7d32" : "#d32f2f"}; }
        code { font-size: 12px; }
      </style>
      <ha-card>
        <div class="camera-wrap">${this._cameraMarkup(cameraEntity)}</div>
        <div class="body">
          <div class="title">${this._deviceName()}</div>
          <div class="subtitle"><span class="pill">${online ? "online" : "offline"}</span> ${deviceId ? `<code>${deviceId}</code>` : "brak device_id"}</div>
          <div class="row">
            <button class="call" id="call" ${inCall || !online || !deviceId ? "disabled" : ""}>Zadzwoń / mów</button>
            <button class="hangup" id="hangup" ${!inCall ? "disabled" : ""}>Rozłącz</button>
          </div>
          <div class="status">${this._status}</div>
          <audio id="remote-audio" autoplay playsinline></audio>
        </div>
      </ha-card>`;
    this.shadowRoot.getElementById("call")?.addEventListener("click", () => this._call());
    this.shadowRoot.getElementById("hangup")?.addEventListener("click", () => this._hangup(true));
  }
}

customElements.define("oldphonekiosk-intercom-card", OldPhoneKioskIntercomCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "oldphonekiosk-intercom-card",
  name: "OldPhoneKiosk Intercom Card",
  description: "Camera + WebRTC two-way intercom for OldPhoneKiosk panels",
});
