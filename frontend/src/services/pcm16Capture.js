const WORKLET_URL = "/pcm16-worklet.js";

function emitWithAck(socket, event, payload) {
  return new Promise((resolve) => socket.emit(event, payload, resolve));
}

/**
 * Capture mono microphone audio, resample it to 16 kHz PCM16, and send it to
 * the A2 Socket.IO boundary. Call stop() when the turn or room ends.
 */
export async function startPcm16Capture({ socket, playerId, matchId, guestId, onError }) {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
  });
  try {
    const started = await emitWithAck(socket, "transcription:start", {
      player_id: playerId,
      ...(matchId ? { match_id: matchId, guest_id: guestId } : {}),
    });
    if (!started?.ok) {
      throw new Error(started?.error?.message ?? "Could not start transcription.");
    }

    const context = new AudioContext();
    await context.audioWorklet.addModule(WORKLET_URL);
    const source = context.createMediaStreamSource(stream);
    const processor = new AudioWorkletNode(context, "pcm16-worklet", {
      processorOptions: {
        sampleRate: started.sample_rate,
        chunkMs: started.chunk_ms,
      },
    });
    const silentSink = context.createGain();
    silentSink.gain.value = 0;

    const handleError = (payload) => onError?.(payload.message);
    socket.on("transcription:error", handleError);
    processor.port.onmessage = ({ data }) => {
      socket.emit("transcription:audio", data, (response) => {
        if (!response?.ok) onError?.(response?.error?.message ?? "Audio was rejected.");
      });
    };
    source.connect(processor).connect(silentSink).connect(context.destination);

    return {
      async stop() {
        processor.port.onmessage = null;
        source.disconnect();
        processor.disconnect();
        silentSink.disconnect();
        stream.getTracks().forEach((track) => track.stop());
        socket.off("transcription:error", handleError);
        await context.close();
        await emitWithAck(socket, "transcription:stop", {});
      },
    };
  } catch (error) {
    stream.getTracks().forEach((track) => track.stop());
    throw error;
  }
}
