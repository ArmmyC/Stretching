/* Drop-in sound effects for YUEDMAI.
   Add files in /static/sounds with the names below; missing files are ignored. */
(function () {
  "use strict";

  const SOUND_PATHS = {
    button: "/static/sounds/button.mp3",
    countdown: "/static/sounds/countdown.mp3",
    stretch: "/static/sounds/stretch.mp3",
    complete: "/static/sounds/complete.mp3",
  };

  const VOLUMES = {
    button: 0.45,
    countdown: 0.7,
    stretch: 0.35,
    complete: 0.8,
  };

  const sounds = {};

  function createAudio(name) {
    if (sounds[name]) return sounds[name];
    const audio = new Audio(SOUND_PATHS[name]);
    audio.preload = "auto";
    audio.volume = VOLUMES[name] || 0.6;
    audio.loop = name === "stretch";
    audio.addEventListener("error", () => {
      sounds[name].available = false;
    });
    sounds[name] = audio;
    sounds[name].available = true;
    return sounds[name];
  }

  Object.keys(SOUND_PATHS).forEach(createAudio);

  function tryPlay(audio) {
    if (!audio || audio.available === false) return;
    const result = audio.play();
    if (result && typeof result.catch === "function") {
      result.catch(() => {
        /* Browser may block audio until the first user gesture. */
      });
    }
  }

  function play(name, options) {
    const audio = createAudio(name);
    if (!audio || audio.available === false) return;
    if (options && options.restart !== false) {
      try {
        audio.currentTime = 0;
      } catch (error) {
        /* Some browsers block seeking before metadata loads. */
      }
    }
    tryPlay(audio);
  }

  function playLoop(name) {
    const audio = createAudio(name);
    if (!audio || audio.available === false || !audio.paused) return;
    tryPlay(audio);
  }

  function stop(name) {
    const audio = createAudio(name);
    if (!audio) return;
    audio.pause();
    try {
      audio.currentTime = 0;
    } catch (error) {
      /* Ignore unsupported seek during early load. */
    }
  }

  function pause(name) {
    const audio = createAudio(name);
    if (audio) audio.pause();
  }

  function unlockAudio() {
    Object.values(sounds).forEach((audio) => {
      if (!audio || audio.available === false) return;
      audio.load();
    });
  }

  document.addEventListener("pointerdown", unlockAudio, { once: true });
  document.addEventListener("keydown", unlockAudio, { once: true });

  document.addEventListener("click", (event) => {
    if (event.target.closest("button, a, [data-action]")) play("button");
  });

  ["YUEDMAI:hardware", "yuedmai:hardware", "stretchsense:hardware"].forEach((eventName) => {
    window.addEventListener(eventName, () => play("button"));
  });

  window.addEventListener("beforeunload", () => stop("stretch"));
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) pause("stretch");
  });

  window.StretchAudio = {
    play,
    playLoop,
    stop,
    pause,
  };
})();
