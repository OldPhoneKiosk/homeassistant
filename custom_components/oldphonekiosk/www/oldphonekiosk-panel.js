class OldPhoneKioskPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._devices = [];
    this._status = "Gotowy";
    this._sessionId = null;
    this._pc = null;
    this._localStream = null;
    this._selectedDevice = "";
    this._unsubscribe = null;
  }

  set hass(hass) {
    this._hass = hass;
    const devices = Object.values(hass.states)
      .filter((state) => state.entity_id.startsWith("binary_sensor.") && state.attributes.bridge_device_id && state.attributes.friendly_name?.toLowerCase().includes("online"))
      .map((state) => ({
        deviceId: state.attributes.bridge_device_id,
        name: (state.attributes.friendly_name || state.entity_id).replace(/ online$/i, ""),
        online: state.state === "on",
      }));
    const unique = [];
    const seen = new Set();
    for (const device of devices) {
      if (!seen.has(device.deviceId)) {
        seen.add(device.deviceId);
        unique.push(device);
      }
    }
    this._devices = unique;
    if (!this._selectedDevice && unique.length) this._selectedDevice = unique[0].deviceId;
    this.render();
  }

  connectedCallback() {
    this.render();
  }

  disconnectedCallback() {
    this._hangup(false);
  }

  async _call() {
    if (!this._hass || !this._selectedDevice) return;
    try {
      this._status = "Proszę o mikrofon…";
      this.render();
      this._localStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        video: false,
      });
      this._pc = new RTCPeerConnection({ iceServers: [] });
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
        device_id: this._selectedDevice,
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

  render() {
    if (!this.shadowRoot) return;
    const options = this._devices.map((d) => `<option value="${d.deviceId}" ${d.deviceId === this._selectedDevice ? "selected" : ""}>${d.name} ${d.online ? "●" : "○"}</option>`).join("");
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; padding: 24px; font-family: var(--paper-font-body1_-_font-family, sans-serif); }
        .card { max-width: 720px; padding: 20px; border-radius: 16px; background: var(--card-background-color, #fff); box-shadow: var(--ha-card-box-shadow, 0 2px 8px #0002); }
        h1 { margin: 0 0 12px; font-size: 24px; }
        p { color: var(--secondary-text-color, #666); }
        select, button { font-size: 16px; padding: 12px; margin: 8px 8px 8px 0; border-radius: 10px; }
        button.primary { background: var(--primary-color, #03a9f4); color: white; border: 0; }
        button.danger { background: #d32f2f; color: white; border: 0; }
        .status { margin-top: 12px; font-weight: 600; }
      </style>
      <div class="card">
        <h1>OldPhoneKiosk interkom</h1>
        <p>Rozmowa audio działa przez WebRTC. Przeglądarka HA poprosi o mikrofon; iPad odtworzy dźwięk i odeśle swój mikrofon.</p>
        <label>Panel:</label>
        <select id="device">${options}</select>
        <div>
          <button class="primary" id="call" ${this._sessionId ? "disabled" : ""}>Zadzwoń</button>
          <button class="danger" id="hangup" ${!this._sessionId ? "disabled" : ""}>Rozłącz</button>
        </div>
        <div class="status">${this._status}</div>
        <audio id="remote-audio" autoplay playsinline></audio>
      </div>`;
    this.shadowRoot.getElementById("device")?.addEventListener("change", (ev) => {
      this._selectedDevice = ev.target.value;
    });
    this.shadowRoot.getElementById("call")?.addEventListener("click", () => this._call());
    this.shadowRoot.getElementById("hangup")?.addEventListener("click", () => this._hangup(true));
  }
}
customElements.define("oldphonekiosk-panel", OldPhoneKioskPanel);
