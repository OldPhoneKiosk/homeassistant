class OldPhoneKioskIntercomCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._status = "Gotowy";
    this._sessionId = null;
    this._pc = null;
    this._localStream = null;
    this._audioSender = null;
    this._unsubscribe = null;
    this._statsTimer = null;
    this._busy = false;
    this._ipadDiagnostics = "";
  }

  static getStubConfig() {
    return { type: "custom:oldphonekiosk-intercom-card", entity: "binary_sensor.ipad_online" };
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
    this._cleanupMedia();
  }

  getCardSize() {
    return this._config.camera_entity ? 6 : 3;
  }

  _deviceId() {
    if (this._config.device_id) return this._config.device_id;
    const state = this._hass?.states?.[this._config.entity];
    return state?.attributes?.bridge_device_id || state?.attributes?.device_id || "";
  }

  _stateByEntity(entityId) {
    return entityId ? this._hass?.states?.[entityId] : undefined;
  }

  _cameraEntity() {
    if (this._config.camera_entity) return this._config.camera_entity;
    const configured = this._config.entity;
    if (configured?.startsWith("camera.")) return configured;
    const deviceId = this._deviceId();
    if (!deviceId || !this._hass) return "";
    const candidates = Object.entries(this._hass.states)
      .filter(([entityId, state]) => {
        if (!entityId.startsWith("camera.")) return false;
        return state.attributes?.bridge_device_id === deviceId || state.attributes?.device_id === deviceId;
      })
      .map(([entityId]) => entityId);
    return candidates[0] || "";
  }

  _deviceName() {
    const state = this._stateByEntity(this._config.entity) || this._stateByEntity(this._cameraEntity());
    return this._config.name || state?.attributes?.friendly_name?.replace(/ online$/i, "") || this._deviceId() || "OldPhoneKiosk";
  }

  _online() {
    const state = this._stateByEntity(this._config.entity);
    if (!state) return true;
    if (state.entity_id?.startsWith("binary_sensor.")) return state.state === "on";
    return state.state !== "unavailable" && state.state !== "unknown";
  }

  async _call() {
    if (this._busy) return;
    if (!this._hass) return;
    const deviceId = this._deviceId();
    if (!deviceId) {
      this._setError("Brak device_id. Dodaj w YAML: device_id: <wartość z encji/camera attributes bridge_device_id>.");
      return;
    }
    this._busy = true;
    try {
      this._status = "Startuję interkom, kamerę i głośnik…";
      this.render();
      this._pc = new RTCPeerConnection({ iceServers: this._config.ice_servers || [] });
      const audioTransceiver = this._pc.addTransceiver("audio", { direction: "sendrecv" });
      this._audioSender = audioTransceiver.sender;
      this._pc.ontrack = (event) => {
        const audio = this.shadowRoot.getElementById("remote-audio");
        if (!audio) return;
        const stream = event.streams?.[0] || new MediaStream([event.track]);
        audio.srcObject = stream;
        audio.muted = false;
        audio.play().catch((err) => {
          this._status = `Audio z iPada wymaga kliknięcia/głośnika: ${err?.message || err}`;
          this.render();
        });
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
      const hasLocalAudio = await this._ensureLocalAudio();
      if (!hasLocalAudio) {
        throw new Error("Nie udało się przygotować mikrofonu HA przed zestawieniem WebRTC");
      }
      const start = await this._hass.callWS({
        type: "oldphonekiosk/intercom/start",
        device_id: deviceId,
      });
      this._sessionId = start.session_id;
      this._status = "Sesja HA OK — zestawiam WebRTC…";
      this.render();
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
      this._status = "Interkom i kamera startują — czekam na iPada…";
      this.render();
    } catch (err) {
      await this._hangup(false, { status: `Błąd: ${err?.message || err}` });
    } finally {
      this._busy = false;
      this.render();
    }
  }

  async _handleSignal(frame) {
    if (!this._pc || frame.session_id !== this._sessionId) return;
    if (frame.action === "answer" && frame.sdp) {
      await this._pc.setRemoteDescription({ type: "answer", sdp: frame.sdp });
      const direction = this._audioDirectionFromSdp(frame.sdp);
      this._status = `Połączono — iPad audio: ${direction || "nieznane"}; przytrzymaj Mów`;
      this._startInboundAudioStats();
      this.render();
      return;
    }
    if (frame.action === "ice_candidate" && frame.candidate) {
      await this._pc.addIceCandidate(frame.candidate);
      return;
    }
    if (frame.action === "hangup") {
      await this._hangup(false, { status: "Rozłączono przez iPada" });
      return;
    }
    if (frame.action === "audio_diagnostics") {
      this._ipadDiagnostics = this._formatIpadDiagnostics(frame.diagnostics || {});
      this.render();
      return;
    }
    if (frame.action === "error") {
      await this._hangup(false, { status: `Błąd iPada: ${frame.error || "Błąd interkomu"}` });
    }
  }

  _formatIpadDiagnostics(diagnostics) {
    const keys = ["stage", "isActive", "inputAvailable", "inputChannels", "preferredInput", "currentInputs", "currentOutputs", "availableInputs", "category", "mode"];
    return keys
      .filter((key) => diagnostics[key] !== undefined && diagnostics[key] !== "")
      .map((key) => `${key}=${diagnostics[key]}`)
      .join("; ");
  }

  _audioDirectionFromSdp(sdp) {
    const lines = String(sdp || "").split(/\r?\n/);
    let inAudio = false;
    for (const line of lines) {
      if (line.startsWith("m=")) inAudio = line.startsWith("m=audio");
      if (inAudio && ["a=sendrecv", "a=sendonly", "a=recvonly", "a=inactive"].includes(line)) {
        return line.slice(2);
      }
    }
    return "unknown";
  }

  _startInboundAudioStats() {
    if (this._statsTimer) clearInterval(this._statsTimer);
    this._statsTimer = setInterval(async () => {
      if (!this._pc || !this._sessionId) return;
      try {
        const stats = await this._pc.getStats();
        for (const report of stats.values()) {
          if (report.type === "inbound-rtp" && report.kind === "audio") {
            const bytes = report.bytesReceived ?? 0;
            const packets = report.packetsReceived ?? 0;
            const level = report.audioLevel;
            this._status = `iPad→HA RTP bytes=${bytes} packets=${packets}${level !== undefined ? ` level=${level}` : ""}`;
            this.render();
            return;
          }
        }
        this._status = "iPad→HA: brak inbound-rtp audio w stats";
        this.render();
      } catch (_) {}
    }, 2000);
  }

  _setMicEnabled(enabled) {
    this._talking = Boolean(enabled);
    if (this._localStream) {
      for (const track of this._localStream.getAudioTracks()) {
        track.enabled = this._talking;
      }
    }
  }

  async _ensureLocalAudio() {
    if (this._localStream) return true;
    if (!navigator.mediaDevices?.getUserMedia) {
      this._setError("Przeglądarka nie udostępnia mikrofonu dla tej strony. Otwórz Home Assistant przez HTTPS albo zaufany adres lokalny.");
      return false;
    }
    try {
      this._status = "Proszę o mikrofon…";
      this.render();
      this._localStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        video: false,
      });
      this._setMicEnabled(false);
      const track = this._localStream.getAudioTracks()[0];
      if (this._audioSender && track) {
        await this._audioSender.replaceTrack(track);
      }
      return true;
    } catch (err) {
      this._setError(`Mikrofon: ${err?.message || err}`);
      return false;
    }
  }

  async _startTalking(ev) {
    ev?.preventDefault?.();
    if (!this._sessionId) return;
    const hasAudio = await this._ensureLocalAudio();
    if (!hasAudio) return;
    this._setMicEnabled(true);
    window.addEventListener("pointerup", (event) => this._stopTalking(event), { once: true });
    this._status = "Mówisz — puść przycisk, żeby wyciszyć";
    this.render();
  }

  _stopTalking(ev) {
    ev?.preventDefault?.();
    if (!this._localStream) return;
    this._setMicEnabled(false);
    if (this._sessionId) {
      this._status = "Mikrofon wyciszony — przytrzymaj Mów";
    }
    this.render();
  }

  _cleanupMedia() {
    this._talking = false;
    this._sessionId = null;
    this._ipadDiagnostics = "";
    if (this._unsubscribe) {
      this._unsubscribe();
      this._unsubscribe = null;
    }
    if (this._statsTimer) {
      clearInterval(this._statsTimer);
      this._statsTimer = null;
    }
    if (this._pc) {
      this._pc.close();
      this._pc = null;
    }
    this._audioSender = null;
    if (this._localStream) {
      for (const track of this._localStream.getTracks()) track.stop();
      this._localStream = null;
    }
  }

  async _hangup(send = true, options = {}) {
    const sessionId = this._sessionId;
    // Send the remote hangup before local cleanup. Local cleanup unsubscribes from
    // the HA signaling stream, and that unsubscribe also removes the broker
    // session; doing it first made the following hangup hit "unknown session" and
    // the iPad never received stop_intercom/stop_stream.
    if (send && sessionId && this._hass) {
      await this._hass.callWS({ type: "oldphonekiosk/intercom/hangup", session_id: sessionId }).catch(() => {});
    }
    this._cleanupMedia();
    this._status = options.status || "Rozłączono";
    this.render();
  }

  _setError(err) {
    this._status = `Błąd: ${err?.message || err}`;
    this.render();
  }

  _absoluteUrl(url) {
    if (!url) return "";
    if (/^https?:\/\//i.test(url)) return url;
    return this._hass?.hassUrl(url) || url;
  }

  _cameraMarkup(cameraEntity) {
    if (!cameraEntity || !this._hass?.states?.[cameraEntity]) return "";
    const camera = this._hass.states[cameraEntity];
    const attrs = camera.attributes || {};
    const hasPanelVideoUrl = Object.prototype.hasOwnProperty.call(attrs, "video_url");
    const source = hasPanelVideoUrl ? attrs.video_url : attrs.entity_picture;
    if (!source) {
      return `<div class="camera-placeholder">${cameraEntity}<br><small>Kamera wystartuje po kliknięciu Zadzwoń</small></div>`;
    }
    return `<img class="camera" src="${this._absoluteUrl(source)}" alt="${attrs.friendly_name || cameraEntity}" />`;
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
        .subtitle { color: var(--secondary-text-color); font-size: 13px; margin-bottom: 12px; word-break: break-word; }
        .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
        button { cursor: pointer; border: 0; border-radius: 10px; padding: 10px 14px; font-weight: 600; }
        button.call { background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #fff); }
        button.talk { background: var(--success-color, #2e7d32); color: #fff; min-width: 96px; touch-action: none; user-select: none; }
        button.talk.active { filter: brightness(1.18); transform: scale(.98); box-shadow: inset 0 0 0 3px rgba(255,255,255,.35); }
        button.hangup { background: var(--error-color, #db4437); color: #fff; }
        button:disabled { opacity: .45; cursor: not-allowed; }
        .status { margin-top: 12px; font-size: 13px; color: var(--secondary-text-color); }
        .diag { margin-top: 6px; font-size: 11px; color: var(--secondary-text-color); word-break: break-word; }
        .status.error { color: var(--error-color, #db4437); font-weight: 600; }
        .pill { display: inline-block; border-radius: 999px; padding: 2px 8px; font-size: 12px; background: ${online ? "rgba(46, 125, 50, .14)" : "rgba(211, 47, 47, .14)"}; color: ${online ? "#2e7d32" : "#d32f2f"}; }
        code { font-size: 12px; }
      </style>
      <ha-card>
        <div class="camera-wrap">${this._cameraMarkup(cameraEntity)}</div>
        <div class="body">
          <div class="title">${this._deviceName()}</div>
          <div class="subtitle"><span class="pill">${online ? "online" : "offline"}</span> ${deviceId ? `<code>${deviceId}</code>` : "brak device_id"}</div>
          <div class="row">
            <button class="call" id="call" ${this._busy || inCall || !online || !deviceId ? "disabled" : ""}>${this._busy ? "Łączę…" : "Zadzwoń"}</button>
            <button class="talk ${this._talking ? "active" : ""}" id="talk" ${!inCall || this._busy ? "disabled" : ""}>Mów</button>
            <button class="hangup" id="hangup" ${!inCall ? "disabled" : ""}>Rozłącz</button>
          </div>
          <div class="status ${this._status.startsWith("Błąd") ? "error" : ""}">${this._status}</div>
          ${this._ipadDiagnostics ? `<div class="diag">iPad audio route: ${this._ipadDiagnostics}</div>` : ""}
          <audio id="remote-audio" autoplay playsinline></audio>
        </div>
      </ha-card>`;
    this.shadowRoot.getElementById("call")?.addEventListener("click", () => this._call());
    const talk = this.shadowRoot.getElementById("talk");
    talk?.addEventListener("pointerdown", (ev) => this._startTalking(ev));
    talk?.addEventListener("pointerup", (ev) => this._stopTalking(ev));
    talk?.addEventListener("pointercancel", (ev) => this._stopTalking(ev));
    talk?.addEventListener("pointerleave", (ev) => this._stopTalking(ev));
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
