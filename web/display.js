/**
 * MeowBot Display Agent — Canvas-based cat display for 360x360 round screen.
 *
 * Concept: "Living Cat in a Round Window"
 * - Boot: cat approaches from its inner world
 * - Idle: full cat figure in its world (breathing, blinking, tail)
 * - Listening: close-up cat eyes, ears perked up
 * - Thinking: cat turns away, walks into its world
 * - Speaking: close-up eyes animate with speech
 * - Sleep: cat curls up, eyes close, screen dims
 *
 * Copyright 2026 MeowBot Team. Apache-2.0.
 */

// ── Constants ──
const W = 360;
const H = 360;
const CX = W / 2;  // center x
const CY = H / 2;  // center y
const R = W / 2;    // radius

const IDLE_TIMEOUT_MS = 120000; // 2 min → sleep
const BOOT_DURATION_MS = 3000;  // longer for Cheshire smile effect
const TRANSITION_MS = 500;

// Colors (kawaii dark theme)
const C = {
  bg: '#0d0d1a',
  bgIdle: '#111128',
  bgWarm: '#1a1020',
  fur: '#e8dcc8',
  furDark: '#c4b49a',
  furShadow: '#9e8e74',
  nose: '#ffb6c1',
  eyeWhite: '#f0f0f0',
  eyeOuter: '#88cc44',
  eyeInner: '#446622',
  pupil: '#111111',
  whisker: '#d4c4a8',
  mouth: '#cc8899',
  earInner: '#ffccdd',
  accent: '#e94560',
  stars: '#ffffff',
};

// ── Easing ──
function easeInOut(t) {
  return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
}
function easeOut(t) {
  return 1 - Math.pow(1 - t, 3);
}
function lerp(a, b, t) {
  return a + (b - a) * t;
}

// ── Main Class ──
class DisplayAgent {
  constructor(canvas, options = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.onTouchEvent = options.onTouchEvent || (() => {});

    this.state = 'off';
    this.prevState = 'off';
    this.stateTime = 0;        // ms since entering current state
    this.transitionProgress = 1; // 0..1, 1 = fully in current state
    this.lastTimestamp = 0;
    this.running = false;

    // Idle timers
    this.idleTimer = 0;
    this.lastActivity = Date.now();

    // Cat animation params
    this.cat = {
      x: CX,
      y: CY + 30,
      scale: 1,
      breathPhase: 0,
      blinkTimer: 0,
      blinkDuration: 0,
      isBlinking: false,
      tailPhase: 0,
      earAngle: 0,
      eyeOpenness: 1,     // 0=closed, 1=open
      pupilDilation: 0.5, // 0=slit, 1=wide
      pupilX: 0,          // -1..1 look direction
      pupilY: 0,
      mouthOpen: 0,       // 0=closed, 1=open
      bodyAngle: 0,       // rotation for turning away
    };

    // Gesture state for thinking depth
    this.thinkingDepth = 0; // 0=near, 1=far away

    // Touch gesture recognition
    this._setupTouch();

    // Cheshire Cat smile phase
    this._cheshirePhase = 0; // 0..1 for boot, used for Cheshire smile effect

    // Idle behavior scheduler
    this._nextIdleBehavior = 0;
    this._currentIdleBehavior = null;
    this._idleBehaviorTime = 0;

    // Touch reaction overlay
    this._touchReaction = null;
    this._touchReactionTime = 0;

    // Speaking animation
    this._speakPhase = 0;

    // Emotion state from server
    this.emotionState = null; // {primary, intensity, valence, arousal, intent}
    this._emotionGlow = { r: 0.5, g: 0.3, b: 0.7 }; // current glow RGB (normalized)
    this._targetGlow = { r: 0.5, g: 0.3, b: 0.7 };  // target glow RGB
  }

  // ── Public API ──

  start() {
    if (this.running) return;
    this.running = true;
    this.lastTimestamp = performance.now();
    this._loop(this.lastTimestamp);
  }

  stop() {
    this.running = false;
  }

  setState(newState) {
    if (newState === this.state) return;
    this.prevState = this.state;
    this.state = newState;
    this.stateTime = 0;
    this.transitionProgress = 0;
    this.lastActivity = Date.now();

    // State-specific initialization
    if (newState === 'idle') {
      this._nextIdleBehavior = 2000; // first behavior after 2s
    }
    if (newState === 'boot') {
      this.cat.scale = 0.1;
      this.cat.eyeOpenness = 0;
    }
    if (newState === 'thinking') {
      this.thinkingDepth = 0;
    }
  }

  /**
   * Called from test_client's ws.onmessage to infer display state.
   */
  onWebSocketMessage(msg) {
    switch (msg.type) {
      case 'hello':
        // Server responded → boot animation
        if (this.state === 'off' || this.state === 'sleep') {
          this.setState('boot');
        }
        break;
      case 'stt':
        // STT result received → switch to thinking
        if (msg.text) this.setState('thinking');
        break;
      case 'llm':
        // Claude responded — stay in thinking until audio actually plays.
        // playAudio() onplay event will call setState('speaking').
        break;
      case 'tts_end':
        // Audio chunks received — playAudio() handles display via onplay/onended.
        break;
      case 'emotion':
        // Emotion detected from user's speech/text
        this.emotionState = msg;
        this._targetGlow = this._emotionToGlow(msg.primary, msg.intensity);
        break;
      case 'error':
        // Error → back to idle
        if (this.state === 'thinking' || this.state === 'speaking') {
          this.setState('idle');
        }
        break;
    }
  }

  /**
   * Map emotion to glow color (RGB normalized 0-1).
   */
  _emotionToGlow(primary, intensity = 0.7) {
    const glows = {
      happy:     { r: 1.0, g: 0.84, b: 0.0 },  // warm gold
      sad:       { r: 0.29, g: 0.56, b: 0.85 },  // cool blue
      angry:     { r: 0.91, g: 0.27, b: 0.37 },  // red
      neutral:   { r: 0.5,  g: 0.3,  b: 0.7 },   // soft purple
      surprised: { r: 0.9,  g: 0.9,  b: 1.0 },   // bright white
      fear:      { r: 0.53, g: 0.81, b: 0.92 },   // pale blue
    };
    return glows[primary] || glows.neutral;
  }

  /**
   * Called when user starts mic or sends text.
   */
  setListening() {
    if (this.state === 'idle' || this.state === 'sleep') {
      this.setState('listening');
    }
  }

  /**
   * Called when user sends text (direct to thinking since no STT).
   */
  setThinking() {
    this.setState('thinking');
  }

  /**
   * Called on disconnect.
   */
  setOff() {
    this.setState('sleep');
    setTimeout(() => { if (this.state === 'sleep') this.setState('off'); }, 2000);
  }

  // ── Render Loop ──

  _loop(timestamp) {
    if (!this.running) return;

    const dt = timestamp - this.lastTimestamp;
    this.lastTimestamp = timestamp;
    this.stateTime += dt;

    // Update transition
    if (this.transitionProgress < 1) {
      this.transitionProgress = Math.min(1, this.stateTime / TRANSITION_MS);
    }

    // Check idle timeout
    if (this.state === 'idle' && Date.now() - this.lastActivity > IDLE_TIMEOUT_MS) {
      this.setState('sleep');
    }

    this._update(dt);
    this._render();

    requestAnimationFrame((t) => this._loop(t));
  }

  // ── Update (animation logic) ──

  _update(dt) {
    const cat = this.cat;
    const t = easeInOut(this.transitionProgress);

    // Always update breathing and tail
    cat.breathPhase += dt * 0.002;
    cat.tailPhase += dt * 0.003;

    // Smooth glow color transition (emotion-driven) — FAST for visible effect
    const glowSpeed = 0.008;
    this._emotionGlow.r = lerp(this._emotionGlow.r, this._targetGlow.r, glowSpeed * dt);
    this._emotionGlow.g = lerp(this._emotionGlow.g, this._targetGlow.g, glowSpeed * dt);
    this._emotionGlow.b = lerp(this._emotionGlow.b, this._targetGlow.b, glowSpeed * dt);

    // Emotion DRAMATICALLY modulates cat during speaking/idle
    if (this.emotionState && (this.state === 'speaking' || this.state === 'idle')) {
      const emo = this.emotionState;
      const lerpSpeed = 0.08; // fast, visible changes

      switch (emo.primary) {
        case 'happy':
          cat.pupilDilation = lerp(cat.pupilDilation, 0.8, lerpSpeed);
          cat.eyeOpenness = cat.isBlinking ? 0.1 : lerp(cat.eyeOpenness, 1.1, lerpSpeed);
          cat.earAngle = lerp(cat.earAngle, -0.15, lerpSpeed); // ears perked up
          cat.mouthOpen = lerp(cat.mouthOpen, 0.15, lerpSpeed); // slight smile
          break;
        case 'sad':
          cat.pupilDilation = lerp(cat.pupilDilation, 0.25, lerpSpeed);
          cat.eyeOpenness = cat.isBlinking ? 0.1 : lerp(cat.eyeOpenness, 0.5, lerpSpeed); // droopy
          cat.earAngle = lerp(cat.earAngle, 0.3, lerpSpeed);  // ears down
          cat.mouthOpen = lerp(cat.mouthOpen, 0, lerpSpeed);
          break;
        case 'angry':
          cat.pupilDilation = lerp(cat.pupilDilation, 0.15, lerpSpeed); // narrow slits
          cat.eyeOpenness = cat.isBlinking ? 0.1 : lerp(cat.eyeOpenness, 0.7, lerpSpeed); // squinting
          cat.earAngle = lerp(cat.earAngle, 0.4, lerpSpeed);  // ears back/flat
          cat.mouthOpen = lerp(cat.mouthOpen, 0, lerpSpeed);
          break;
        case 'surprised':
          cat.pupilDilation = lerp(cat.pupilDilation, 1.0, lerpSpeed); // wide pupils
          cat.eyeOpenness = cat.isBlinking ? 0.1 : lerp(cat.eyeOpenness, 1.3, lerpSpeed); // wide open
          cat.earAngle = lerp(cat.earAngle, -0.25, lerpSpeed); // ears very perked
          cat.mouthOpen = lerp(cat.mouthOpen, 0.2, lerpSpeed);
          break;
        case 'fear':
          cat.pupilDilation = lerp(cat.pupilDilation, 0.9, lerpSpeed);
          cat.eyeOpenness = cat.isBlinking ? 0.1 : lerp(cat.eyeOpenness, 1.15, lerpSpeed);
          cat.earAngle = lerp(cat.earAngle, 0.5, lerpSpeed); // ears flat
          cat.mouthOpen = lerp(cat.mouthOpen, 0.05, lerpSpeed);
          break;
        default: // neutral
          cat.earAngle = lerp(cat.earAngle, 0, lerpSpeed * 0.5);
          cat.mouthOpen = lerp(cat.mouthOpen, 0, lerpSpeed * 0.5);
          break;
      }
    }

    // Blinking logic
    cat.blinkTimer -= dt;
    if (cat.blinkTimer <= 0 && !cat.isBlinking && this.state !== 'sleep') {
      cat.isBlinking = true;
      cat.blinkDuration = 150;
      cat.blinkTimer = 150;
    }
    if (cat.isBlinking) {
      cat.blinkTimer -= 0; // already decremented
      if (cat.blinkTimer <= 0) {
        cat.isBlinking = false;
        cat.blinkTimer = 2000 + Math.random() * 4000;
      }
    }

    // State-specific updates
    switch (this.state) {
      case 'boot':
        // Cheshire Cat effect: smile appears first (0-1s), then face fades in (1-2s), then full body (2-3s)
        this._cheshirePhase = Math.min(1, this.stateTime / BOOT_DURATION_MS);
        if (this.stateTime < 1000) {
          // Phase 1: only smile visible
          cat.scale = 0.8;
          cat.eyeOpenness = 0;
          cat.mouthOpen = 0.2;
        } else if (this.stateTime < 2000) {
          // Phase 2: eyes appear, nose appears
          const p = (this.stateTime - 1000) / 1000;
          cat.scale = 0.8;
          cat.eyeOpenness = easeOut(p);
          cat.pupilDilation = 0.7;
        } else {
          // Phase 3: full body scales in
          const p = (this.stateTime - 2000) / 1000;
          cat.scale = lerp(0.8, 0.55, easeOut(p));
          cat.eyeOpenness = 1;
        }
        if (this.stateTime > BOOT_DURATION_MS) {
          this.setState('idle');
        }
        break;

      case 'idle':
        cat.scale = lerp(cat.scale, 0.55, 0.05);
        cat.eyeOpenness = cat.isBlinking ? 0.1 : lerp(cat.eyeOpenness, 1, 0.1);
        cat.pupilDilation = lerp(cat.pupilDilation, 0.5, 0.05);
        cat.bodyAngle = lerp(cat.bodyAngle, 0, 0.05);
        cat.earAngle = lerp(cat.earAngle, 0, 0.1);
        cat.mouthOpen = lerp(cat.mouthOpen, 0, 0.1);
        this._updateIdleBehavior(dt);
        break;

      case 'listening':
        // Zoom to close-up eyes
        cat.scale = lerp(cat.scale, 1.8, 0.08);
        cat.eyeOpenness = cat.isBlinking ? 0.1 : lerp(cat.eyeOpenness, 1.1, 0.1);
        cat.pupilDilation = lerp(cat.pupilDilation, 0.7, 0.08);
        cat.earAngle = lerp(cat.earAngle, -0.15, 0.1); // ears forward
        cat.bodyAngle = lerp(cat.bodyAngle, 0, 0.05);
        break;

      case 'thinking':
        // Cat shrinks quickly to full body, then turns and walks into its world
        this.thinkingDepth = Math.min(1, this.thinkingDepth + dt * 0.0015);
        const depth = easeInOut(this.thinkingDepth);
        // Fast zoom out: scale drops from current to 0.45 in first 30%, then to 0.3
        if (this.thinkingDepth < 0.3) {
          cat.scale = lerp(cat.scale, 0.45, 0.12);
        } else {
          cat.scale = lerp(0.45, 0.3, (depth - 0.3) / 0.7);
        }
        cat.bodyAngle = lerp(0, Math.PI, Math.min(1, depth * 1.5));
        cat.eyeOpenness = lerp(cat.eyeOpenness, 0.7, 0.08);
        cat.pupilDilation = 0.3;
        cat.earAngle = lerp(cat.earAngle, 0.1, 0.05);
        // Small wandering while thinking
        cat.pupilX = Math.sin(this.stateTime * 0.003) * 0.3;
        break;

      case 'speaking':
        // Close-up eyes — cat "returns" with the answer
        cat.scale = lerp(cat.scale, 1.8, 0.12);  // fast zoom in
        cat.bodyAngle = lerp(cat.bodyAngle, 0, 0.12); // fast turn back
        cat.eyeOpenness = cat.isBlinking ? 0.1 : lerp(cat.eyeOpenness, 1, 0.15);
        cat.pupilDilation = lerp(cat.pupilDilation, 0.6, 0.08);
        cat.earAngle = lerp(cat.earAngle, -0.05, 0.1); // ears slightly forward
        // Mouth moves rhythmically
        this._speakPhase += dt * 0.01;
        cat.mouthOpen = 0.15 + Math.abs(Math.sin(this._speakPhase * 3)) * 0.25;
        break;

      case 'sleep':
        cat.scale = lerp(cat.scale, 0.45, 0.03);
        cat.eyeOpenness = lerp(cat.eyeOpenness, 0, 0.05);
        cat.pupilDilation = 0.2;
        cat.mouthOpen = 0;
        cat.earAngle = lerp(cat.earAngle, 0.2, 0.05); // ears relaxed
        break;

      case 'off':
        break;
    }

    // Update touch reaction
    if (this._touchReaction) {
      this._touchReactionTime += dt;
      if (this._touchReactionTime > 1500) {
        this._touchReaction = null;
      }
    }
  }

  _updateIdleBehavior(dt) {
    this._nextIdleBehavior -= dt;
    if (this._nextIdleBehavior <= 0 && !this._currentIdleBehavior) {
      // Pick a random behavior
      const behaviors = ['look_around', 'ear_twitch', 'tail_wag', 'yawn'];
      this._currentIdleBehavior = behaviors[Math.floor(Math.random() * behaviors.length)];
      this._idleBehaviorTime = 0;
      this._nextIdleBehavior = 5000 + Math.random() * 10000;
    }

    if (this._currentIdleBehavior) {
      this._idleBehaviorTime += dt;
      const cat = this.cat;
      const progress = Math.min(1, this._idleBehaviorTime / 1000);

      switch (this._currentIdleBehavior) {
        case 'look_around':
          cat.pupilX = Math.sin(progress * Math.PI * 2) * 0.5;
          cat.pupilY = Math.cos(progress * Math.PI * 1.5) * 0.3;
          break;
        case 'ear_twitch':
          cat.earAngle = Math.sin(progress * Math.PI * 4) * 0.15;
          break;
        case 'tail_wag':
          // tail handled in render via tailPhase acceleration
          break;
        case 'yawn':
          if (progress < 0.5) {
            cat.mouthOpen = easeOut(progress * 2) * 0.4;
            cat.eyeOpenness = 1 - easeOut(progress * 2) * 0.5;
          } else {
            cat.mouthOpen = lerp(0.4, 0, (progress - 0.5) * 2);
            cat.eyeOpenness = lerp(0.5, 1, (progress - 0.5) * 2);
          }
          break;
      }

      if (this._idleBehaviorTime > 1200) {
        this._currentIdleBehavior = null;
        this.cat.pupilX = lerp(this.cat.pupilX, 0, 0.3);
        this.cat.pupilY = lerp(this.cat.pupilY, 0, 0.3);
      }
    }
  }

  // ── Render ──

  _render() {
    const ctx = this.ctx;
    ctx.save();

    // Clear with circle clip
    ctx.clearRect(0, 0, W, H);
    ctx.beginPath();
    ctx.arc(CX, CY, R, 0, Math.PI * 2);
    ctx.clip();

    // Background
    this._drawBackground(ctx);

    // Cheshire smile (boot phase 1: smile before cat appears)
    if (this.state === 'boot' && this.stateTime < 1200) {
      this._drawCheshireSmile(ctx, Math.min(1, this.stateTime / 800));
    }

    // Cheshire smile (sleep: smile fades last)
    if (this.state === 'sleep' && this.stateTime > 1500) {
      const fadeOut = 1 - Math.min(1, (this.stateTime - 1500) / 2000);
      if (fadeOut > 0.05) {
        this._drawCheshireSmile(ctx, fadeOut);
      }
    }

    // Cat
    if (this.state !== 'off') {
      // During boot phase 1, cat body is invisible (only smile shows)
      if (this.state === 'boot' && this.stateTime < 800) {
        // Don't draw cat body yet — only Cheshire smile
      } else {
        this._drawCat(ctx);
      }
    }

    // Touch reaction overlay
    if (this._touchReaction) {
      this._drawTouchReaction(ctx);
    }

    // Sleep dimming overlay
    if (this.state === 'sleep') {
      const dimAlpha = Math.min(0.6, this.stateTime / 3000 * 0.6);
      ctx.fillStyle = `rgba(0, 0, 0, ${dimAlpha})`;
      ctx.fillRect(0, 0, W, H);

      // Zzz
      if (this.stateTime > 2000) {
        const zAlpha = Math.min(1, (this.stateTime - 2000) / 1000);
        ctx.fillStyle = `rgba(255, 255, 255, ${zAlpha * 0.4})`;
        ctx.font = '24px sans-serif';
        const zY = CY - 40 - Math.sin(this.stateTime * 0.001) * 10;
        ctx.fillText('z z z', CX + 30, zY);
      }
    }

    // Off state = black
    if (this.state === 'off') {
      ctx.fillStyle = '#000';
      ctx.fillRect(0, 0, W, H);
    }

    ctx.restore();
  }

  _drawBackground(ctx) {
    // Gradient background based on state
    let bgTop, bgBottom;
    switch (this.state) {
      case 'boot':
        bgTop = '#0a0a20';
        bgBottom = '#1a1030';
        break;
      case 'idle':
        bgTop = '#111128';
        bgBottom = '#1e1535';
        break;
      case 'listening':
      case 'speaking':
        bgTop = '#0d1530';
        bgBottom = '#1a1040';
        break;
      case 'thinking':
        bgTop = '#0a0a20';
        bgBottom = '#15102a';
        break;
      case 'sleep':
        bgTop = '#050510';
        bgBottom = '#0a0a18';
        break;
      default:
        bgTop = C.bg;
        bgBottom = C.bg;
    }

    const grad = ctx.createRadialGradient(CX, CY, 0, CX, CY, R);
    grad.addColorStop(0, bgBottom);
    grad.addColorStop(1, bgTop);
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, W, H);

    // Emotion glow overlay — VIVID ambient light reflecting emotion
    if (this.emotionState && this.state !== 'off' && this.state !== 'sleep') {
      const g = this._emotionGlow;
      const intensity = (this.emotionState.intensity || 0.5) * 0.4; // strong, visible
      const glowGrad = ctx.createRadialGradient(CX, CY, 0, CX, CY, R);
      const r = Math.round(g.r * 255);
      const gr = Math.round(g.g * 255);
      const b = Math.round(g.b * 255);
      glowGrad.addColorStop(0, `rgba(${r},${gr},${b},${intensity})`);
      glowGrad.addColorStop(1, `rgba(${r},${gr},${b},0)`);
      ctx.fillStyle = glowGrad;
      ctx.fillRect(0, 0, W, H);
    }

    // Stars/particles in idle and thinking
    if (this.state === 'idle' || this.state === 'thinking' || this.state === 'sleep') {
      this._drawStars(ctx);
    }

    // Simple "room" elements in idle (floor line, window)
    if (this.state === 'idle' && this.cat.scale < 0.7) {
      ctx.strokeStyle = 'rgba(255,255,255,0.05)';
      ctx.lineWidth = 1;
      // Floor
      ctx.beginPath();
      ctx.moveTo(0, CY + 100);
      ctx.lineTo(W, CY + 100);
      ctx.stroke();
    }
  }

  _drawStars(ctx) {
    // Deterministic stars based on seed
    const starCount = this.state === 'sleep' ? 20 : 8;
    for (let i = 0; i < starCount; i++) {
      const seed = i * 137.508;
      const sx = (Math.sin(seed) * 0.5 + 0.5) * W;
      const sy = (Math.cos(seed * 1.3) * 0.5 + 0.5) * H * 0.6;
      const twinkle = 0.3 + Math.sin(this.stateTime * 0.001 + seed) * 0.3;
      const size = 1 + (i % 3) * 0.5;

      ctx.beginPath();
      ctx.arc(sx, sy, size, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255, 255, 255, ${twinkle})`;
      ctx.fill();
    }
  }

  _drawCat(ctx) {
    const cat = this.cat;
    const scale = cat.scale;
    const breath = Math.sin(cat.breathPhase) * 2;

    ctx.save();
    ctx.translate(CX, CY + 30);
    ctx.rotate(cat.bodyAngle > Math.PI / 2 ? 0 : 0); // front-facing always in render
    ctx.scale(scale, scale);

    if (scale > 1.2) {
      // Close-up mode: draw only eyes
      this._drawCloseUpEyes(ctx, breath);
    } else {
      // Full body mode
      this._drawFullBody(ctx, breath);
    }

    ctx.restore();
  }

  // ── Full Body Drawing ──

  _drawFullBody(ctx, breath) {
    const cat = this.cat;
    const facingBack = cat.bodyAngle > Math.PI / 2;

    // Tail
    this._drawTail(ctx, breath, facingBack);

    // Body
    ctx.fillStyle = C.fur;
    ctx.beginPath();
    ctx.ellipse(0, 20 + breath, 55, 65, 0, 0, Math.PI * 2);
    ctx.fill();

    // Body shadow
    ctx.fillStyle = C.furDark;
    ctx.beginPath();
    ctx.ellipse(0, 40 + breath, 45, 30, 0, 0, Math.PI);
    ctx.fill();

    // Head
    ctx.fillStyle = C.fur;
    ctx.beginPath();
    ctx.arc(0, -45 + breath, 45, 0, Math.PI * 2);
    ctx.fill();

    // Ears
    this._drawEars(ctx, breath, facingBack);

    if (!facingBack) {
      // Face (front-facing)
      this._drawFace(ctx, breath);
    } else {
      // Back of head — just ears and back markings
      ctx.fillStyle = C.furDark;
      ctx.beginPath();
      ctx.arc(0, -45 + breath, 20, 0, Math.PI * 2);
      ctx.fill();
    }

    // Paws
    ctx.fillStyle = C.furDark;
    ctx.beginPath();
    ctx.ellipse(-25, 75 + breath, 18, 10, -0.1, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.ellipse(25, 75 + breath, 18, 10, 0.1, 0, Math.PI * 2);
    ctx.fill();
  }

  _drawTail(ctx, breath, facingBack) {
    const cat = this.cat;
    const tailSwing = Math.sin(cat.tailPhase) * 20;

    ctx.strokeStyle = C.fur;
    ctx.lineWidth = 10;
    ctx.lineCap = 'round';
    ctx.beginPath();
    const side = facingBack ? 1 : -1;
    ctx.moveTo(side * 35, 50 + breath);
    ctx.quadraticCurveTo(
      side * (60 + tailSwing), 20 + breath,
      side * (55 + tailSwing * 1.5), -20 + breath
    );
    ctx.stroke();

    // Tail tip
    ctx.strokeStyle = C.furDark;
    ctx.lineWidth = 8;
    ctx.beginPath();
    ctx.moveTo(side * (55 + tailSwing * 1.3), -10 + breath);
    ctx.quadraticCurveTo(
      side * (58 + tailSwing * 1.5), -20 + breath,
      side * (55 + tailSwing * 1.5), -25 + breath
    );
    ctx.stroke();
  }

  _drawEars(ctx, breath, facingBack) {
    const cat = this.cat;
    const earRotation = cat.earAngle;

    // Left ear
    ctx.save();
    ctx.translate(-30, -80 + breath);
    ctx.rotate(-0.3 + earRotation);
    ctx.fillStyle = C.fur;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(-15, -30);
    ctx.lineTo(15, -5);
    ctx.closePath();
    ctx.fill();
    if (!facingBack) {
      ctx.fillStyle = C.earInner;
      ctx.beginPath();
      ctx.moveTo(0, -2);
      ctx.lineTo(-10, -22);
      ctx.lineTo(10, -5);
      ctx.closePath();
      ctx.fill();
    }
    ctx.restore();

    // Right ear
    ctx.save();
    ctx.translate(30, -80 + breath);
    ctx.rotate(0.3 - earRotation);
    ctx.fillStyle = C.fur;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(15, -30);
    ctx.lineTo(-15, -5);
    ctx.closePath();
    ctx.fill();
    if (!facingBack) {
      ctx.fillStyle = C.earInner;
      ctx.beginPath();
      ctx.moveTo(0, -2);
      ctx.lineTo(10, -22);
      ctx.lineTo(-10, -5);
      ctx.closePath();
      ctx.fill();
    }
    ctx.restore();
  }

  _drawFace(ctx, breath) {
    const cat = this.cat;
    const eyeY = -50 + breath;
    const eyeSpacing = 22;

    // Eyes
    this._drawEye(ctx, -eyeSpacing, eyeY, false);
    this._drawEye(ctx, eyeSpacing, eyeY, true);

    // Nose
    ctx.fillStyle = C.nose;
    ctx.beginPath();
    ctx.moveTo(0, -35 + breath);
    ctx.lineTo(-5, -30 + breath);
    ctx.lineTo(5, -30 + breath);
    ctx.closePath();
    ctx.fill();

    // Mouth
    const mouthOpen = cat.mouthOpen;
    ctx.strokeStyle = C.mouth;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(0, -30 + breath);
    ctx.lineTo(0, -27 + breath + mouthOpen * 5);
    ctx.stroke();

    // Smile curves
    ctx.beginPath();
    ctx.arc(-6, -27 + breath, 6, 0, Math.PI * 0.5);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(6, -27 + breath, 6, Math.PI * 0.5, Math.PI);
    ctx.stroke();

    // Whiskers
    ctx.strokeStyle = C.whisker;
    ctx.lineWidth = 1;
    for (let side = -1; side <= 1; side += 2) {
      for (let i = 0; i < 3; i++) {
        const angle = (i - 1) * 0.15;
        ctx.beginPath();
        ctx.moveTo(side * 15, -32 + breath + i * 4);
        ctx.lineTo(side * 55, -38 + breath + i * 6 + angle * 20);
        ctx.stroke();
      }
    }
  }

  _drawEye(ctx, x, y, isRight) {
    const cat = this.cat;
    const openness = cat.eyeOpenness;
    if (openness < 0.05) return; // fully closed

    const eyeH = 14 * openness;
    const eyeW = 10;

    // Eye white
    ctx.fillStyle = C.eyeWhite;
    ctx.beginPath();
    ctx.ellipse(x, y, eyeW, eyeH, 0, 0, Math.PI * 2);
    ctx.fill();

    // Iris — color shifts with emotion (small eyes too)
    const irisH = eyeH * 0.85;
    const irisW = eyeW * 0.8;
    const sEmo = this.emotionState ? this.emotionState.primary : 'neutral';
    let sIrisColor = C.eyeOuter;
    if (sEmo === 'sad') sIrisColor = '#5588cc';
    else if (sEmo === 'angry') sIrisColor = '#cc5544';
    else if (sEmo === 'happy') sIrisColor = '#aacc44';
    else if (sEmo === 'surprised') sIrisColor = '#44cccc';
    else if (sEmo === 'fear') sIrisColor = '#8888cc';
    ctx.fillStyle = sIrisColor;
    ctx.beginPath();
    ctx.ellipse(x + cat.pupilX * 3, y + cat.pupilY * 2, irisW, irisH, 0, 0, Math.PI * 2);
    ctx.fill();

    // Pupil (vertical slit — cat-style!)
    const pupilW = 2 + cat.pupilDilation * 4;
    const pupilH = irisH * 0.9;
    ctx.fillStyle = C.pupil;
    ctx.beginPath();
    ctx.ellipse(x + cat.pupilX * 3, y + cat.pupilY * 2, pupilW, pupilH, 0, 0, Math.PI * 2);
    ctx.fill();

    // Eye highlight
    ctx.fillStyle = 'rgba(255,255,255,0.7)';
    ctx.beginPath();
    ctx.arc(x + 3 + cat.pupilX * 2, y - 4, 2.5, 0, Math.PI * 2);
    ctx.fill();
  }

  // ── Close-Up Eyes (Conversation Mode) ──

  _drawCloseUpEyes(ctx, breath) {
    const cat = this.cat;
    const openness = cat.eyeOpenness;
    const eyeSpacing = 65;
    const eyeY = -10 + breath * 0.5;

    // Left eye
    this._drawLargeEye(ctx, -eyeSpacing, eyeY, openness, false);
    // Right eye
    this._drawLargeEye(ctx, eyeSpacing, eyeY, openness, true);

    // Nose hint (small, at bottom)
    if (openness > 0.5) {
      ctx.fillStyle = C.nose;
      ctx.globalAlpha = 0.6;
      ctx.beginPath();
      ctx.moveTo(0, 50 + breath);
      ctx.lineTo(-8, 60 + breath);
      ctx.lineTo(8, 60 + breath);
      ctx.closePath();
      ctx.fill();
      ctx.globalAlpha = 1;

      // Whisker hints
      ctx.strokeStyle = C.whisker;
      ctx.lineWidth = 1.5;
      ctx.globalAlpha = 0.4;
      for (let side = -1; side <= 1; side += 2) {
        ctx.beginPath();
        ctx.moveTo(side * 20, 55 + breath);
        ctx.lineTo(side * 80, 45 + breath);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(side * 20, 60 + breath);
        ctx.lineTo(side * 80, 60 + breath);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }

    // Ears peeking from top
    this._drawLargeEars(ctx, breath);
  }

  _drawLargeEye(ctx, x, y, openness, isRight) {
    const cat = this.cat;
    if (openness < 0.05) {
      // Closed eye — just a line
      ctx.strokeStyle = C.furDark;
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(x - 35, y);
      ctx.quadraticCurveTo(x, y + 5, x + 35, y);
      ctx.stroke();
      return;
    }

    const eyeH = 42 * openness;
    const eyeW = 32;

    // Eye shape (almond/cat-like)
    ctx.fillStyle = C.eyeWhite;
    ctx.beginPath();
    ctx.ellipse(x, y, eyeW, eyeH, 0, 0, Math.PI * 2);
    ctx.fill();

    // Outer ring
    ctx.strokeStyle = C.furDark;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.ellipse(x, y, eyeW + 1, eyeH + 1, 0, 0, Math.PI * 2);
    ctx.stroke();

    // Iris
    const irisR = eyeH * 0.8;
    const irisW = eyeW * 0.75;
    const px = cat.pupilX * 8;
    const py = cat.pupilY * 5;

    // Iris gradient — color shifts with emotion
    const emo = this.emotionState ? this.emotionState.primary : 'neutral';
    let irisOuter = C.eyeOuter;   // default green
    let irisInner = C.eyeInner;
    let irisEdge = '#335511';
    if (emo === 'sad')       { irisOuter = '#5588cc'; irisInner = '#334466'; irisEdge = '#223355'; }
    else if (emo === 'angry')    { irisOuter = '#cc5544'; irisInner = '#662222'; irisEdge = '#441111'; }
    else if (emo === 'happy')    { irisOuter = '#aacc44'; irisInner = '#557722'; irisEdge = '#446611'; }
    else if (emo === 'surprised'){ irisOuter = '#44cccc'; irisInner = '#226666'; irisEdge = '#115555'; }
    else if (emo === 'fear')     { irisOuter = '#8888cc'; irisInner = '#444466'; irisEdge = '#333355'; }

    const irisGrad = ctx.createRadialGradient(x + px, y + py, 0, x + px, y + py, irisR);
    irisGrad.addColorStop(0, irisInner);
    irisGrad.addColorStop(0.6, irisOuter);
    irisGrad.addColorStop(1, irisEdge);
    ctx.fillStyle = irisGrad;
    ctx.beginPath();
    ctx.ellipse(x + px, y + py, irisW, irisR, 0, 0, Math.PI * 2);
    ctx.fill();

    // Pupil — vertical slit (cat!)
    const pupilW = 4 + cat.pupilDilation * 12;
    const pupilH = irisR * 0.92;
    ctx.fillStyle = C.pupil;
    ctx.beginPath();
    ctx.ellipse(x + px, y + py, pupilW, pupilH, 0, 0, Math.PI * 2);
    ctx.fill();

    // Eye highlight (big)
    ctx.fillStyle = 'rgba(255,255,255,0.8)';
    ctx.beginPath();
    ctx.arc(x + 10 + px * 0.5, y - 12, 6, 0, Math.PI * 2);
    ctx.fill();

    // Small secondary highlight
    ctx.fillStyle = 'rgba(255,255,255,0.4)';
    ctx.beginPath();
    ctx.arc(x - 8 + px * 0.3, y + 10, 3, 0, Math.PI * 2);
    ctx.fill();

    // Eyelid (partial close for squinting)
    if (openness < 0.8) {
      const lidAmount = 1 - openness;
      ctx.fillStyle = C.fur;
      ctx.beginPath();
      ctx.ellipse(x, y - eyeH * (1 - lidAmount * 0.8), eyeW + 5, eyeH * lidAmount, 0, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  _drawLargeEars(ctx, breath) {
    const cat = this.cat;
    const earAngle = cat.earAngle;

    // Left ear
    ctx.save();
    ctx.translate(-55, -85 + breath);
    ctx.rotate(-0.2 + earAngle);
    ctx.fillStyle = C.fur;
    ctx.beginPath();
    ctx.moveTo(0, 20);
    ctx.lineTo(-20, -25);
    ctx.lineTo(25, 5);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = C.earInner;
    ctx.beginPath();
    ctx.moveTo(0, 15);
    ctx.lineTo(-14, -16);
    ctx.lineTo(18, 5);
    ctx.closePath();
    ctx.fill();
    ctx.restore();

    // Right ear
    ctx.save();
    ctx.translate(55, -85 + breath);
    ctx.rotate(0.2 - earAngle);
    ctx.fillStyle = C.fur;
    ctx.beginPath();
    ctx.moveTo(0, 20);
    ctx.lineTo(20, -25);
    ctx.lineTo(-25, 5);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = C.earInner;
    ctx.beginPath();
    ctx.moveTo(0, 15);
    ctx.lineTo(14, -16);
    ctx.lineTo(-18, 5);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }

  // ── Cheshire Cat Smile ──

  _drawCheshireSmile(ctx, alpha) {
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.translate(CX, CY + 10);

    // Glowing smile curve
    const glowSize = 3 + Math.sin(this.stateTime * 0.005) * 1;

    // Outer glow
    ctx.strokeStyle = `rgba(233, 69, 96, ${alpha * 0.3})`;
    ctx.lineWidth = glowSize + 4;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.arc(0, 0, 40, 0.15 * Math.PI, 0.85 * Math.PI);
    ctx.stroke();

    // Main smile
    ctx.strokeStyle = C.nose;
    ctx.lineWidth = glowSize;
    ctx.beginPath();
    ctx.arc(0, 0, 40, 0.15 * Math.PI, 0.85 * Math.PI);
    ctx.stroke();

    // Smile ends curve up (cat-like)
    ctx.lineWidth = glowSize - 1;
    ctx.beginPath();
    ctx.arc(-38, -6, 8, 0.5 * Math.PI, 1.2 * Math.PI);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(38, -6, 8, 1.8 * Math.PI, 2.5 * Math.PI);
    ctx.stroke();

    // Small sparkle near smile
    if (alpha > 0.5) {
      const sparkle = Math.sin(this.stateTime * 0.008) * 0.5 + 0.5;
      ctx.fillStyle = `rgba(255, 200, 220, ${sparkle * alpha})`;
      ctx.beginPath();
      ctx.arc(50, -15, 2, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.arc(-48, -20, 1.5, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.restore();
  }

  // ── Touch Reactions ──

  _drawTouchReaction(ctx) {
    const reaction = this._touchReaction;
    const t = Math.min(1, this._touchReactionTime / 1000);
    const alpha = 1 - easeOut(t);

    ctx.save();
    ctx.globalAlpha = alpha;

    switch (reaction) {
      case 'purr':
        // Hearts float up
        for (let i = 0; i < 3; i++) {
          const hx = CX - 30 + i * 30;
          const hy = CY - 20 - t * 60 - i * 15;
          const size = 8 + i * 2;
          ctx.fillStyle = C.accent;
          ctx.font = `${size}px sans-serif`;
          ctx.fillText('\u2665', hx, hy);
        }
        break;

      case 'surprise':
        // Exclamation marks
        ctx.fillStyle = '#ffcc00';
        ctx.font = `${20 + t * 10}px sans-serif`;
        ctx.fillText('!', CX + 50, CY - 60);
        ctx.fillText('?', CX - 60, CY - 55);
        break;

      case 'sleepy':
        // Extra Zzz
        ctx.fillStyle = 'rgba(255,255,255,0.5)';
        ctx.font = '18px sans-serif';
        ctx.fillText('z z z', CX + 20, CY - 50 - t * 30);
        break;

      case 'play':
        // Sparkles
        for (let i = 0; i < 5; i++) {
          const angle = (i / 5) * Math.PI * 2 + t * 3;
          const dist = 50 + t * 30;
          const sx = CX + Math.cos(angle) * dist;
          const sy = CY + Math.sin(angle) * dist;
          ctx.fillStyle = i % 2 ? '#ffcc00' : C.accent;
          ctx.font = '12px sans-serif';
          ctx.fillText('\u2726', sx, sy);
        }
        break;

      case 'meow':
        // Speech bubble with "Mew!"
        ctx.fillStyle = 'rgba(255,255,255,0.9)';
        const bx = CX + 40, by = CY - 70;
        ctx.beginPath();
        ctx.ellipse(bx, by, 35, 18, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#333';
        ctx.font = 'bold 14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Mew!', bx, by + 5);
        ctx.textAlign = 'start';
        break;
    }

    ctx.restore();
  }

  // ── Touch / Gesture Detection ──

  _setupTouch() {
    const canvas = this.canvas;
    let startX, startY, startTime;
    let points = [];
    let lastTapTime = 0;
    let longPressTimer = null;

    const getPos = (e) => {
      const rect = canvas.getBoundingClientRect();
      const scaleX = W / rect.width;
      const scaleY = H / rect.height;
      const clientX = e.touches ? e.touches[0].clientX : e.clientX;
      const clientY = e.touches ? e.touches[0].clientY : e.clientY;
      return {
        x: (clientX - rect.left) * scaleX,
        y: (clientY - rect.top) * scaleY,
      };
    };

    const isInCircle = (x, y) => {
      const dx = x - CX, dy = y - CY;
      return dx * dx + dy * dy <= R * R;
    };

    const onStart = (e) => {
      e.preventDefault();
      const pos = getPos(e);
      if (!isInCircle(pos.x, pos.y)) return;

      startX = pos.x;
      startY = pos.y;
      startTime = Date.now();
      points = [pos];

      longPressTimer = setTimeout(() => {
        this._onGesture('long_press', pos);
        longPressTimer = null;
      }, 800);
    };

    const onMove = (e) => {
      e.preventDefault();
      if (startX == null) return;
      const pos = getPos(e);
      points.push(pos);

      const dist = Math.hypot(pos.x - startX, pos.y - startY);
      if (dist > 10 && longPressTimer) {
        clearTimeout(longPressTimer);
        longPressTimer = null;
      }
    };

    const onEnd = (e) => {
      e.preventDefault();
      if (startX == null) return;

      if (longPressTimer) {
        clearTimeout(longPressTimer);
        longPressTimer = null;
      }

      const endTime = Date.now();
      const duration = endTime - startTime;
      const pos = points[points.length - 1] || { x: startX, y: startY };
      const totalDist = Math.hypot(pos.x - startX, pos.y - startY);

      if (totalDist < 10 && duration < 200) {
        // Tap or double-tap
        if (endTime - lastTapTime < 300) {
          this._onGesture('double_tap', pos);
          lastTapTime = 0;
        } else {
          lastTapTime = endTime;
          setTimeout(() => {
            if (lastTapTime === endTime) {
              this._onGesture('tap', pos);
            }
          }, 310);
        }
      } else if (totalDist > 30 && duration < 1000) {
        // Stroke or circle?
        if (this._isCircleGesture(points)) {
          this._onGesture('circle', pos);
        } else {
          this._onGesture('stroke', pos);
        }
      }

      startX = startY = null;
      points = [];
    };

    // Mouse events
    canvas.addEventListener('mousedown', onStart);
    canvas.addEventListener('mousemove', onMove);
    canvas.addEventListener('mouseup', onEnd);
    canvas.addEventListener('mouseleave', onEnd);

    // Touch events
    canvas.addEventListener('touchstart', onStart, { passive: false });
    canvas.addEventListener('touchmove', onMove, { passive: false });
    canvas.addEventListener('touchend', onEnd, { passive: false });
  }

  _isCircleGesture(points) {
    if (points.length < 10) return false;

    // Calculate total angle traversed
    let totalAngle = 0;
    const cx = points.reduce((s, p) => s + p.x, 0) / points.length;
    const cy = points.reduce((s, p) => s + p.y, 0) / points.length;

    for (let i = 1; i < points.length; i++) {
      const a1 = Math.atan2(points[i - 1].y - cy, points[i - 1].x - cx);
      const a2 = Math.atan2(points[i].y - cy, points[i].x - cx);
      let da = a2 - a1;
      if (da > Math.PI) da -= Math.PI * 2;
      if (da < -Math.PI) da += Math.PI * 2;
      totalAngle += da;
    }

    return Math.abs(totalAngle) > 5; // ~286 degrees
  }

  _onGesture(gesture, pos) {
    this.lastActivity = Date.now();

    // Wake from sleep on tap
    if (this.state === 'sleep' && gesture === 'tap') {
      this.setState('boot');
      return;
    }

    // Visual reaction
    const reactions = {
      'tap': 'surprise',
      'double_tap': 'meow',
      'long_press': 'sleepy',
      'stroke': 'purr',
      'circle': 'play',
    };

    this._touchReaction = reactions[gesture] || 'surprise';
    this._touchReactionTime = 0;

    // Animate cat response
    const cat = this.cat;
    switch (gesture) {
      case 'tap':
        cat.pupilDilation = 0.9;
        cat.eyeOpenness = 1.2;
        break;
      case 'double_tap':
        cat.earAngle = -0.2;
        cat.mouthOpen = 0.3;
        break;
      case 'long_press':
        cat.eyeOpenness = 0.3;
        cat.mouthOpen = 0.3;
        break;
      case 'stroke':
        cat.eyeOpenness = 0.5;
        cat.pupilDilation = 0.8;
        break;
      case 'circle':
        cat.tailPhase += 5;
        break;
    }

    // Emit to WebSocket
    this.onTouchEvent({ type: 'touch_event', gesture, position: pos });
  }
}

// Export for use in test_client.html
window.DisplayAgent = DisplayAgent;
