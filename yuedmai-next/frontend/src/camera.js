export async function startCamera(videoElement) {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    throw new Error("Camera access is not available in this browser.");
  }

  const stream = await navigator.mediaDevices.getUserMedia({
    video: {
      width: { ideal: 960 },
      height: { ideal: 540 },
      facingMode: "user",
    },
    audio: false,
  });

  videoElement.srcObject = stream;
  await videoElement.play();
  return stream;
}

export function frameHint(videoElement, holdSeconds) {
  return {
    width: videoElement.videoWidth || 0,
    height: videoElement.videoHeight || 0,
    holdSeconds,
    timestamp: Date.now(),
  };
}
