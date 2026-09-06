import { useEffect, useRef, useState } from "react";

const initialDevices = { camera: true, microphone: true };

function permissionMessage(error) {
  if (error?.name === "NotAllowedError") {
    return "Camera and microphone access was blocked. Allow both in your browser, then try again.";
  }
  if (error?.name === "NotFoundError") {
    return "We could not find a camera or microphone. Connect a device, then try again.";
  }
  return "We could not start your camera and microphone. Please try again.";
}

// This callback stays local to the page flow and is supplied by HomePage.
// eslint-disable-next-line react/prop-types
export function MediaRoom({ onLeave }) {
  const previewRef = useRef(null);
  const streamRef = useRef(null);
  const [permissionState, setPermissionState] = useState("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [devices, setDevices] = useState(initialDevices);

  const stopPreview = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (previewRef.current) previewRef.current.srcObject = null;
  };

  useEffect(() => stopPreview, []);

  useEffect(() => {
    if (previewRef.current && streamRef.current) {
      previewRef.current.srcObject = streamRef.current;
    }
  }, [permissionState]);

  const requestDevices = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setErrorMessage("This browser does not support camera and microphone access.");
      setPermissionState("error");
      return;
    }

    setPermissionState("requesting");
    setErrorMessage("");
    stopPreview();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      streamRef.current = stream;
      setDevices(initialDevices);
      setPermissionState("ready");
    } catch (error) {
      setErrorMessage(permissionMessage(error));
      setPermissionState("error");
    }
  };

  const toggleDevice = (device) => {
    const kind = device === "camera" ? "video" : "audio";
    const nextEnabled = !devices[device];
    streamRef.current?.getTracks().filter((track) => track.kind === kind).forEach((track) => {
      track.enabled = nextEnabled;
    });
    setDevices((current) => ({ ...current, [device]: nextEnabled }));
  };

  const leaveRoom = () => {
    stopPreview();
    onLeave();
  };

  const hasPreview = permissionState === "ready";

  return (
    <main className="media-page">
      <header className="guest-banner">
        <span className="guest-banner__spark">✦</span>
        <span>Media check · your camera and microphone stay in your control.</span>
        <button className="guest-banner__claim" type="button" onClick={leaveRoom}>LEAVE</button>
      </header>
      <section className="media-room" aria-label="Camera and microphone setup">
        <button className="round-icon round-icon--left" type="button" onClick={leaveRoom} aria-label="Leave media setup">×</button>
        <div className="media-stage">
          <div className="media-heading">
            <p>ROUND ONE · MEDIA CHECK</p>
            <h1>GET READY<br /><span>TO IMPROVISE.</span></h1>
            <div className="media-status"><i className={hasPreview ? "media-status__dot media-status__dot--ready" : "media-status__dot"} />{hasPreview ? "CAMERA + MIC READY" : "CAMERA + MIC REQUIRED"}</div>
          </div>

          <div className="video-grid">
            <article className="video-tile video-tile--local">
              <video ref={previewRef} autoPlay muted playsInline className={hasPreview ? "" : "video-tile__hidden"} />
              {!hasPreview && <div className="video-placeholder"><b>YOU</b><span>{permissionState === "requesting" ? "REQUESTING ACCESS…" : "CAMERA PREVIEW"}</span></div>}
              <div className="video-tile__label"><span>YOU</span><b>{devices.microphone && hasPreview ? "● MIC ON" : "○ MIC OFF"}</b></div>
            </article>
            <article className="video-tile video-tile--remote">
              <div className="video-placeholder"><b>PLAYER 7392</b><span>WAITING FOR LIVEKIT ROOM</span></div>
              <div className="video-tile__label"><span>OPPONENT</span><b className="video-tile__waiting">⌁ CONNECTING</b></div>
            </article>
          </div>

          {hasPreview ? (
            <div className="media-controls" aria-label="Media controls">
              <button type="button" className={devices.microphone ? "media-control media-control--active" : "media-control"} onClick={() => toggleDevice("microphone")}>{devices.microphone ? "◉" : "◌"}<span>{devices.microphone ? "MUTE" : "UNMUTE"}</span></button>
              <button type="button" className={devices.camera ? "media-control media-control--active" : "media-control"} onClick={() => toggleDevice("camera")}>{devices.camera ? "◉" : "◌"}<span>{devices.camera ? "CAMERA ON" : "CAMERA OFF"}</span></button>
            </div>
          ) : (
            <button className="match-button media-permission-button" type="button" disabled={permissionState === "requesting"} onClick={requestDevices}><span className="match-button__people">◉</span><span><strong>{permissionState === "requesting" ? "REQUESTING ACCESS" : "ENABLE CAMERA + MIC"}</strong><small>YOU CONTROL WHAT YOU SHARE</small></span></button>
          )}

          {errorMessage && <p className="media-error" role="alert">{errorMessage}</p>}
          <p className="media-connection" role="status"><i />WAITING FOR SECURE ROOM CREDENTIALS · LIVEKIT CONNECTS AFTER THE MATCH SERVICE PROVIDES A TOKEN.</p>
        </div>
      </section>
    </main>
  );
}
