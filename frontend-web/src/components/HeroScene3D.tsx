'use client';

import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';

/**
 * Real-time WebGL hero: a paper shopping bag overflowing with groceries,
 * surrounded by orbiting products. Reacts to pointer, scroll and click.
 *
 * - Pauses when off-screen or when the tab is hidden
 * - Renders a single still frame for `prefers-reduced-motion`
 * - Fails silently (CSS background remains) when WebGL is unavailable
 * - Fully disposes GPU resources on unmount
 */

const PALETTE = {
  paper: 0xfbf6ec,
  ink: 0x182820,
  green: 0x2b4436,
  orange: 0xe8541e,
  yellow: 0xf3ca4f,
  cream: 0xfff0e7,
};

interface Props {
  /** Fewer orbiters + no particles: used on the shop page. */
  lite?: boolean;
  className?: string;
}

interface Orbiter {
  mesh: THREE.Object3D;
  radius: number;
  speed: number;
  phase: number;
  lift: number;
  bob: number;
  spin: THREE.Vector3;
}

function softShadowTexture() {
  const size = 128;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const g = ctx.createRadialGradient(size / 2, size / 2, 4, size / 2, size / 2, size / 2);
  g.addColorStop(0, 'rgba(0,0,0,0.55)');
  g.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

export default function HeroScene3D({ lite = false, className }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    } catch {
      return; // no WebGL: the CSS fallback behind the canvas stays visible
    }

    renderer.setClearColor(0x000000, 0);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.domElement.setAttribute('aria-hidden', 'true');
    renderer.domElement.style.cssText = 'display:block;width:100%;height:100%;touch-action:pan-y;';
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(renderer);
    const envScene = new RoomEnvironment();
    const envTarget = pmrem.fromScene(envScene, 0.04);
    scene.environment = envTarget.texture;
    envScene.traverse((o) => {
      const m = o as THREE.Mesh;
      m.geometry?.dispose?.();
      (m.material as THREE.Material | undefined)?.dispose?.();
    });

    const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);
    camera.position.set(0, 0.3, 8.2);

    const key = new THREE.DirectionalLight(0xfff1d6, 2.4);
    key.position.set(3.5, 5, 5);
    const rim = new THREE.PointLight(PALETTE.orange, 26, 14);
    rim.position.set(-3.6, -0.5, 2.2);
    const fill = new THREE.PointLight(PALETTE.yellow, 10, 12);
    fill.position.set(3.2, 2.2, -2);
    scene.add(key, rim, fill);

    const rig = new THREE.Group();
    scene.add(rig);

    /* ---------- hero bag ---------- */
    const bag = new THREE.Group();
    rig.add(bag);

    const paper = new THREE.MeshPhysicalMaterial({ color: PALETTE.paper, roughness: 0.6, clearcoat: 0.25, clearcoatRoughness: 0.5 });
    const greenMat = new THREE.MeshStandardMaterial({ color: PALETTE.green, roughness: 0.45 });
    const orangeMat = new THREE.MeshPhysicalMaterial({ color: PALETTE.orange, roughness: 0.35, clearcoat: 0.6 });
    const yellowMat = new THREE.MeshPhysicalMaterial({ color: PALETTE.yellow, roughness: 0.4, clearcoat: 0.4 });
    const creamMat = new THREE.MeshStandardMaterial({ color: PALETTE.cream, roughness: 0.5 });
    const goldMat = new THREE.MeshStandardMaterial({ color: 0xe9b949, roughness: 0.25, metalness: 0.9 });

    const body = new THREE.Mesh(new RoundedBoxGeometry(1.8, 2.2, 1, 6, 0.14), paper);
    bag.add(body);

    const band = new THREE.Mesh(new RoundedBoxGeometry(1.84, 0.46, 1.04, 4, 0.09), greenMat);
    band.position.y = -0.62;
    bag.add(band);

    const badge = new THREE.Mesh(new THREE.CylinderGeometry(0.4, 0.4, 0.05, 48), orangeMat);
    badge.rotation.x = Math.PI / 2;
    badge.position.set(0, 0.34, 0.52);
    bag.add(badge);
    const badgeInner = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.06, 32), yellowMat);
    badgeInner.rotation.x = Math.PI / 2;
    badgeInner.position.set(0, 0.34, 0.545);
    bag.add(badgeInner);

    const handleGeo = new THREE.TorusGeometry(0.46, 0.05, 16, 48, Math.PI);
    [-0.24, 0.24].forEach((z) => {
      const h = new THREE.Mesh(handleGeo, greenMat);
      h.position.set(0, 1.1, z);
      bag.add(h);
    });

    // groceries peeking out of the top
    const baguette = new THREE.Mesh(new THREE.CapsuleGeometry(0.17, 1.2, 8, 20), new THREE.MeshStandardMaterial({ color: 0xd9953a, roughness: 0.7 }));
    baguette.position.set(-0.36, 1.35, -0.05);
    baguette.rotation.z = 0.32;
    bag.add(baguette);
    const greens = new THREE.Mesh(new THREE.IcosahedronGeometry(0.36, 1), new THREE.MeshStandardMaterial({ color: 0x6f9f4a, roughness: 0.6, flatShading: true }));
    greens.position.set(0.38, 1.22, 0.05);
    bag.add(greens);
    const tomato = new THREE.Mesh(new THREE.SphereGeometry(0.27, 32, 24), orangeMat);
    tomato.position.set(0.02, 1.12, 0.28);
    bag.add(tomato);

    bag.position.y = -0.1;
    bag.scale.setScalar(1.2);

    /* ---------- soft ground shadow ---------- */
    const shadowTex = softShadowTexture();
    const shadow = new THREE.Mesh(
      new THREE.PlaneGeometry(4.2, 4.2),
      new THREE.MeshBasicMaterial({ map: shadowTex, transparent: true, depthWrite: false, opacity: 0.55 }),
    );
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.y = -1.85;
    rig.add(shadow);

    /* ---------- orbiting products ---------- */
    const orbiters: Orbiter[] = [];
    const addOrbiter = (mesh: THREE.Object3D, o: Omit<Orbiter, 'mesh'>) => {
      rig.add(mesh);
      orbiters.push({ mesh, ...o });
    };

    const orange = new THREE.Mesh(new THREE.SphereGeometry(0.4, 40, 28), orangeMat);
    const crate = new THREE.Mesh(new RoundedBoxGeometry(0.72, 0.72, 0.72, 4, 0.09), yellowMat);
    const can = new THREE.Mesh(new THREE.CylinderGeometry(0.27, 0.27, 0.7, 32), new THREE.MeshStandardMaterial({ color: PALETTE.green, roughness: 0.3, metalness: 0.35 }));
    const donut = new THREE.Mesh(new THREE.TorusGeometry(0.3, 0.13, 20, 48), creamMat);
    const coin = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.42, 0.08, 48), goldMat);
    const gem = new THREE.Mesh(new THREE.OctahedronGeometry(0.38, 0), new THREE.MeshPhysicalMaterial({ color: PALETTE.cream, roughness: 0.15, metalness: 0.1, clearcoat: 1 }));

    addOrbiter(orange, { radius: 3.1, speed: 0.34, phase: 0.2, lift: 0.9, bob: 1.1, spin: new THREE.Vector3(0.2, 0.5, 0) });
    addOrbiter(crate, { radius: 3.4, speed: 0.28, phase: 2.3, lift: -0.6, bob: 0.8, spin: new THREE.Vector3(0.4, 0.6, 0.2) });
    addOrbiter(coin, { radius: 2.8, speed: 0.4, phase: 4.1, lift: 1.5, bob: 1.4, spin: new THREE.Vector3(0.1, 1.4, 0) });
    addOrbiter(can, { radius: 3.3, speed: 0.31, phase: 5.2, lift: -1.1, bob: 1.0, spin: new THREE.Vector3(0.6, 0.2, 0.3) });
    if (!lite) {
      addOrbiter(donut, { radius: 3.0, speed: 0.37, phase: 3.2, lift: 0.1, bob: 0.9, spin: new THREE.Vector3(0.7, 0.4, 0) });
      addOrbiter(gem, { radius: 3.6, speed: 0.25, phase: 1.2, lift: 1.9, bob: 1.2, spin: new THREE.Vector3(0.3, 0.9, 0.4) });
    }
    coin.rotation.x = Math.PI / 2;

    /* ---------- sparkles ---------- */
    let sparkles: THREE.Points | null = null;
    if (!lite) {
      const count = 160;
      const pos = new Float32Array(count * 3);
      for (let i = 0; i < count; i++) {
        const r = 2.4 + Math.random() * 2.6;
        const a = Math.random() * Math.PI * 2;
        pos[i * 3] = Math.cos(a) * r;
        pos[i * 3 + 1] = (Math.random() - 0.5) * 5;
        pos[i * 3 + 2] = Math.sin(a) * r * 0.7;
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      sparkles = new THREE.Points(
        geo,
        new THREE.PointsMaterial({ color: PALETTE.yellow, size: 0.045, transparent: true, opacity: 0.85, depthWrite: false, sizeAttenuation: true }),
      );
      rig.add(sparkles);
    }

    /* ---------- interaction state ---------- */
    const pointer = { x: 0, y: 0, tx: 0, ty: 0 };
    let impulse = 0;
    let scrollShift = 0;

    const onPointerMove = (e: PointerEvent) => {
      const r = host.getBoundingClientRect();
      pointer.tx = ((e.clientX - r.left) / r.width - 0.5) * 2;
      pointer.ty = ((e.clientY - r.top) / r.height - 0.5) * 2;
    };
    const onPointerLeave = () => { pointer.tx = 0; pointer.ty = 0; };
    const onPointerDown = () => { impulse = 1; };
    const onScroll = () => {
      const r = host.getBoundingClientRect();
      scrollShift = THREE.MathUtils.clamp(-r.top / Math.max(r.height, 1), -0.5, 1);
    };

    host.addEventListener('pointermove', onPointerMove);
    host.addEventListener('pointerleave', onPointerLeave);
    host.addEventListener('pointerdown', onPointerDown);
    window.addEventListener('scroll', onScroll, { passive: true });

    /* ---------- sizing ---------- */
    const resize = () => {
      const w = host.clientWidth || 1;
      const h = host.clientHeight || 1;
      const dpr = Math.min(window.devicePixelRatio || 1, w < 600 ? 1.75 : 2);
      renderer.setPixelRatio(dpr);
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      // keep the whole composition visible on narrow / short canvases
      const halfH = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * camera.position.z;
      const halfW = halfH * camera.aspect;
      const fit = Math.min(1.08, halfW / 3.9, halfH / 2.9);
      rig.scale.setScalar(Math.max(fit, 0.42));
      camera.updateProjectionMatrix();
    };
    resize();
    let renderStill: (() => void) | null = null;
    const ro = new ResizeObserver(() => { resize(); renderStill?.(); });
    ro.observe(host);

    /* ---------- animation ---------- */
    let raf = 0;
    let running = false;
    let visible = true;
    let last = performance.now();
    let t = reduced ? 1.4 : 0;

    const frame = (now: number) => {
      const dt = Math.min((now - last) / 1000, 0.05);
      last = now;
      if (!reduced) t += dt;

      pointer.x += (pointer.tx - pointer.x) * 0.06;
      pointer.y += (pointer.ty - pointer.y) * 0.06;
      impulse *= 0.94;

      rig.rotation.y = pointer.x * 0.35;
      rig.rotation.x = pointer.y * 0.12 + scrollShift * 0.35;
      rig.position.y = -scrollShift * 0.9;

      bag.rotation.y = Math.sin(t * 0.55) * 0.55 + pointer.x * 0.25 + impulse * Math.sin(t * 9) * 0.25;
      bag.rotation.z = Math.sin(t * 0.8) * 0.04;
      bag.position.y = -0.1 + Math.sin(t * 1.1) * 0.1;
      shadow.scale.setScalar(1 - Math.sin(t * 1.1) * 0.04);
      baguette.rotation.z = 0.32 + Math.sin(t * 1.3) * 0.04;
      greens.rotation.y = t * 0.6;

      const boost = 1 + impulse * 2.2;
      orbiters.forEach((o) => {
        const a = t * o.speed * boost + o.phase;
        o.mesh.position.set(
          Math.cos(a) * o.radius,
          o.lift + Math.sin(t * 0.9 + o.phase) * 0.28 * o.bob,
          Math.sin(a) * o.radius * 0.55,
        );
        o.mesh.rotation.x += o.spin.x * dt * boost;
        o.mesh.rotation.y += o.spin.y * dt * boost;
        o.mesh.rotation.z += o.spin.z * dt * boost;
      });

      if (sparkles) sparkles.rotation.y = t * 0.05;

      renderer.render(scene, camera);
      if (!host.dataset.ready) host.dataset.ready = '1';
      if (running && !reduced) raf = requestAnimationFrame(frame);
    };

    const start = () => {
      if (running || reduced) return;
      running = true;
      last = performance.now();
      raf = requestAnimationFrame(frame);
    };
    const stop = () => {
      running = false;
      cancelAnimationFrame(raf);
    };
    const sync = () => (visible && !document.hidden ? start() : stop());

    const io = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; sync(); }, { threshold: 0.01 });
    io.observe(host);
    document.addEventListener('visibilitychange', sync);

    if (reduced) {
      renderStill = () => frame(performance.now());
      renderStill();
    } else {
      start();
    }

    return () => {
      stop();
      io.disconnect();
      ro.disconnect();
      document.removeEventListener('visibilitychange', sync);
      host.removeEventListener('pointermove', onPointerMove);
      host.removeEventListener('pointerleave', onPointerLeave);
      host.removeEventListener('pointerdown', onPointerDown);
      window.removeEventListener('scroll', onScroll);

      scene.traverse((obj) => {
        const m = obj as THREE.Mesh | THREE.Points;
        m.geometry?.dispose?.();
        const mat = (m as THREE.Mesh).material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(mat)) mat.forEach((x) => x.dispose());
        else mat?.dispose?.();
      });
      shadowTex.dispose();
      envTarget.dispose();
      pmrem.dispose();
      renderer.dispose();
      renderer.domElement.remove();
      delete host.dataset.ready;
    };
  }, [lite]);

  return <div ref={hostRef} className={className} />;
}
