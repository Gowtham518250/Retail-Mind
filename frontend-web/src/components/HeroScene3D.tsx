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
    const backRim = new THREE.PointLight(0x8ccc72, 18, 12);
    backRim.position.set(1.8, 3.2, -3);
    scene.add(key, rim, fill, backRim);

    const rig = new THREE.Group();
    scene.add(rig);

    const orbitRings = [
      new THREE.Mesh(
        new THREE.TorusGeometry(2.5, 0.012, 8, 144),
        new THREE.MeshBasicMaterial({
          color: PALETTE.yellow,
          transparent: true,
          opacity: 0.28,
          depthWrite: false,
        }),
      ),
      new THREE.Mesh(
        new THREE.TorusGeometry(2.85, 0.009, 8, 144),
        new THREE.MeshBasicMaterial({
          color: PALETTE.cream,
          transparent: true,
          opacity: 0.18,
          depthWrite: false,
        }),
      ),
    ];
    orbitRings[0].rotation.set(1.18, -0.3, -0.2);
    orbitRings[1].rotation.set(0.82, 0.42, 0.28);
    orbitRings[1].scale.set(1, 0.76, 1);
    rig.add(...orbitRings);

    /* ---------- hero bag ---------- */
    const bag = new THREE.Group();
    rig.add(bag);

    const paper = new THREE.MeshPhysicalMaterial({ color: 0xe6d1a9, roughness: 0.7, clearcoat: 0.16, clearcoatRoughness: 0.62 });
    const greenMat = new THREE.MeshStandardMaterial({ color: PALETTE.green, roughness: 0.45 });
    const orangeMat = new THREE.MeshPhysicalMaterial({ color: PALETTE.orange, roughness: 0.35, clearcoat: 0.6 });
    const yellowMat = new THREE.MeshPhysicalMaterial({ color: PALETTE.yellow, roughness: 0.4, clearcoat: 0.4 });
    const creamMat = new THREE.MeshStandardMaterial({ color: PALETTE.cream, roughness: 0.5 });
    const goldMat = new THREE.MeshStandardMaterial({ color: 0xe9b949, roughness: 0.25, metalness: 0.9 });

    const bagShape = new THREE.Shape();
    bagShape.moveTo(-0.82, -1.06);
    bagShape.lineTo(0.82, -1.06);
    bagShape.lineTo(1.02, 1.02);
    bagShape.lineTo(-1.02, 1.02);
    bagShape.closePath();
    const bagGeometry = new THREE.ExtrudeGeometry(bagShape, {
      depth: 0.82,
      bevelEnabled: true,
      bevelSegments: 4,
      steps: 1,
      bevelSize: 0.055,
      bevelThickness: 0.055,
      curveSegments: 8,
    });
    bagGeometry.translate(0, 0, -0.41);
    const body = new THREE.Mesh(bagGeometry, paper);
    bag.add(body);

    const innerTop = new THREE.Mesh(
      new RoundedBoxGeometry(1.9, 0.09, 0.72, 4, 0.035),
      new THREE.MeshStandardMaterial({ color: 0x4a3828, roughness: 0.9 }),
    );
    innerTop.position.set(0, 0.99, 0);
    bag.add(innerTop);

    const band = new THREE.Mesh(new RoundedBoxGeometry(1.82, 0.42, 0.91, 4, 0.09), greenMat);
    band.position.set(0, -0.62, 0.035);
    bag.add(band);

    const labelCanvas = document.createElement('canvas');
    labelCanvas.width = 512;
    labelCanvas.height = 256;
    const labelContext = labelCanvas.getContext('2d');
    if (labelContext) {
      labelContext.fillStyle = '#f7f1df';
      labelContext.beginPath();
      labelContext.roundRect(18, 18, 476, 220, 30);
      labelContext.fill();
      labelContext.fillStyle = '#245b42';
      labelContext.fillRect(46, 52, 10, 152);
      labelContext.font = '700 38px Arial, sans-serif';
      labelContext.letterSpacing = '5px';
      labelContext.fillText('RETAIL', 82, 112);
      labelContext.fillText('MIND', 82, 164);
      labelContext.fillStyle = '#e8541e';
      labelContext.beginPath();
      labelContext.arc(420, 130, 22, 0, Math.PI * 2);
      labelContext.fill();
    }
    const labelTexture = new THREE.CanvasTexture(labelCanvas);
    labelTexture.colorSpace = THREE.SRGBColorSpace;
    const label = new THREE.Mesh(
      new THREE.PlaneGeometry(0.88, 0.44),
      new THREE.MeshStandardMaterial({
        map: labelTexture,
        roughness: 0.72,
        transparent: true,
      }),
    );
    label.position.set(0, 0.18, 0.52);
    bag.add(label);

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
    const greens = new THREE.Group();
    const leafMaterial = new THREE.MeshStandardMaterial({ color: 0x6f9f4a, roughness: 0.58, flatShading: true });
    for (let i = 0; i < 7; i++) {
      const leaf = new THREE.Mesh(
        new THREE.SphereGeometry(0.21, 14, 10),
        leafMaterial,
      );
      const angle = (i / 7) * Math.PI * 2;
      leaf.position.set(Math.cos(angle) * 0.2, Math.sin(angle) * 0.12 + 0.08, Math.sin(angle) * 0.16);
      leaf.scale.set(0.72, 1.35, 0.58);
      leaf.rotation.z = angle;
      greens.add(leaf);
    }
    greens.position.set(0.42, 1.24, 0.08);
    bag.add(greens);
    const tomato = new THREE.Mesh(new THREE.SphereGeometry(0.27, 32, 24), orangeMat);
    tomato.position.set(0.02, 1.12, 0.28);
    bag.add(tomato);
    const lemon = new THREE.Mesh(
      new THREE.SphereGeometry(0.23, 28, 20),
      new THREE.MeshPhysicalMaterial({ color: 0xf3ca4f, roughness: 0.36, clearcoat: 0.4 }),
    );
    lemon.scale.set(1.35, 0.82, 0.88);
    lemon.position.set(0.48, 1.12, 0.34);
    lemon.rotation.z = -0.3;
    bag.add(lemon);

    bag.position.y = -0.1;
    bag.scale.setScalar(1.3);

    /* ---------- soft ground shadow ---------- */
    const shadowTex = softShadowTexture();
    const shadow = new THREE.Mesh(
      new THREE.PlaneGeometry(5.2, 5.2),
      new THREE.MeshBasicMaterial({ map: shadowTex, transparent: true, depthWrite: false, opacity: 0.55 }),
    );
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.y = -1.9;
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
    const coin = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.28, 0.065, 48), goldMat);
    const gem = new THREE.Mesh(new THREE.OctahedronGeometry(0.38, 0), new THREE.MeshPhysicalMaterial({ color: PALETTE.cream, roughness: 0.15, metalness: 0.1, clearcoat: 1 }));
    const orbiterItems = lite
      ? [
          [orange, 2.35, 0.9, 0.2, 0.22],
          [crate, 2.55, -0.65, 2.3, 0.16],
          [coin, 2.2, 1.5, 4.1, 0.26],
          [can, 2.5, -1.05, 5.2, 0.18],
        ] as const
      : [
          [orange, 3.1, 0.9, 0.2, 0.3],
          [crate, 3.4, -0.6, 2.3, 0.22],
          [coin, 2.8, 1.5, 4.1, 0.34],
          [can, 3.3, -1.1, 5.2, 0.25],
        ] as const;
    orbiterItems.forEach(([mesh, radius, lift, phase, bob], index) => {
      addOrbiter(mesh, {
        radius,
        speed: [0.34, 0.28, 0.4, 0.31][index],
        phase,
        lift,
        bob,
        spin: [
          new THREE.Vector3(0.2, 0.5, 0),
          new THREE.Vector3(0.4, 0.6, 0.2),
          new THREE.Vector3(0.1, 1.4, 0),
          new THREE.Vector3(0.6, 0.2, 0.3),
        ][index],
      });
    });
    if (!lite) {
      addOrbiter(donut, { radius: 3.0, speed: 0.37, phase: 3.2, lift: 0.1, bob: 0.26, spin: new THREE.Vector3(0.7, 0.4, 0) });
      addOrbiter(gem, { radius: 3.6, speed: 0.25, phase: 1.2, lift: 1.9, bob: 0.32, spin: new THREE.Vector3(0.3, 0.9, 0.4) });
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
      const fit = Math.min(1.08, halfW / (lite ? 2.55 : 3.15), halfH / 2.75);
      rig.scale.setScalar(Math.max(fit, 0.5));
      rig.position.x = lite ? 0.12 : 0.24;
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

      rig.rotation.y = pointer.x * 0.58 + Math.sin(t * 0.16) * 0.045;
      rig.rotation.x = pointer.y * 0.24 + scrollShift * 0.35;
      rig.position.x = (lite ? 0.12 : 0.24) + pointer.x * 0.24;
      rig.position.y = -scrollShift * 0.9 + Math.sin(t * 0.72) * 0.07;

      bag.rotation.y = Math.sin(t * 0.55) * 0.72 + pointer.x * 0.34 + impulse * Math.sin(t * 9) * 0.3;
      bag.rotation.x = Math.sin(t * 0.47) * 0.075;
      bag.rotation.z = Math.sin(t * 0.8) * 0.075;
      bag.position.y = -0.1 + Math.sin(t * 1.1) * 0.2;
      shadow.scale.setScalar(1 - Math.sin(t * 1.1) * 0.09);
      orbitRings[0].rotation.y = t * 0.11;
      orbitRings[1].rotation.z = -t * 0.07;
      baguette.rotation.z = 0.32 + Math.sin(t * 1.3) * 0.055;
      greens.rotation.y = t * 0.72;

      const boost = 1 + impulse * 2.2;
      orbiters.forEach((o) => {
        const a = t * o.speed * boost + o.phase;
        o.mesh.position.set(
          Math.cos(a) * o.radius,
          o.lift + Math.sin(t * 0.9 + o.phase) * (lite ? 0.72 : 0.62) * o.bob,
          Math.sin(a) * o.radius * 0.72,
        );
        o.mesh.scale.setScalar(1 + Math.sin(t * 1.4 + o.phase) * 0.045);
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
      labelTexture.dispose();
      envTarget.dispose();
      pmrem.dispose();
      renderer.dispose();
      renderer.domElement.remove();
      delete host.dataset.ready;
    };
  }, [lite]);

  return (
    <div ref={hostRef} className={className}>
      <div className="hero3d-fallback" aria-hidden="true">
        <div className="hero3d-fallback-orbit hero3d-fallback-orbit-a" />
        <div className="hero3d-fallback-orbit hero3d-fallback-orbit-b" />
        <div className="hero3d-fallback-shadow" />
        <div className="hero3d-fallback-bag">
          <span className="hero3d-fallback-handle" />
          <span className="hero3d-fallback-produce hero3d-fallback-produce-a" />
          <span className="hero3d-fallback-produce hero3d-fallback-produce-b" />
          <span className="hero3d-fallback-produce hero3d-fallback-produce-c" />
          <span className="hero3d-fallback-label">RETAIL<br />MIND</span>
          <span className="hero3d-fallback-band" />
        </div>
        <span className="hero3d-fallback-item hero3d-fallback-item-a" />
        <span className="hero3d-fallback-item hero3d-fallback-item-b" />
        <span className="hero3d-fallback-item hero3d-fallback-item-c" />
        <span className="hero3d-fallback-item hero3d-fallback-item-d" />
      </div>
    </div>
  );
}
