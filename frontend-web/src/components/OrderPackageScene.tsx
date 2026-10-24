'use client';

import { useEffect, useRef } from 'react';
import { Package } from 'lucide-react';
import * as THREE from 'three';

export default function OrderPackageScene() {
  const hostRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        alpha: true,
        antialias: true,
        powerPreference: 'low-power',
      });
    } catch {
      return;
    }

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    let still = reducedMotion.matches;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 40);
    camera.position.set(0, 0.12, 6.2);

    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.15;
    renderer.domElement.setAttribute('aria-hidden', 'true');
    renderer.domElement.style.cssText = 'display:block;width:100%;height:100%;';
    host.appendChild(renderer.domElement);

    scene.add(new THREE.HemisphereLight(0xfff6df, 0x28513b, 2.1));

    const keyLight = new THREE.DirectionalLight(0xffefcb, 3.2);
    keyLight.position.set(-3, 4, 5);
    scene.add(keyLight);

    const fillLight = new THREE.PointLight(0xd9ed9a, 24, 9);
    fillLight.position.set(3, 1.3, 2);
    scene.add(fillLight);

    const parcel = new THREE.Group();
    const box = new THREE.Group();
    parcel.add(box);
    scene.add(parcel);

    const carton = new THREE.MeshPhysicalMaterial({
      color: 0xc28b55,
      roughness: 0.72,
      clearcoat: 0.08,
    });
    const ribbon = new THREE.MeshPhysicalMaterial({
      color: 0x174a35,
      roughness: 0.36,
      clearcoat: 0.7,
      clearcoatRoughness: 0.22,
    });
    const ribbonEdge = new THREE.MeshStandardMaterial({
      color: 0xd9ed9a,
      roughness: 0.36,
      metalness: 0.18,
    });
    const paper = new THREE.MeshStandardMaterial({
      color: 0xfffdf7,
      roughness: 0.78,
    });

    const body = new THREE.Mesh(new THREE.BoxGeometry(1.52, 1.26, 1.16), carton);
    box.add(body);

    const verticalBand = new THREE.Mesh(
      new THREE.BoxGeometry(0.27, 1.28, 1.18),
      ribbon,
    );
    verticalBand.position.z = 0.008;
    box.add(verticalBand);

    const horizontalBand = new THREE.Mesh(
      new THREE.BoxGeometry(1.54, 0.2, 1.18),
      ribbon,
    );
    horizontalBand.position.z = 0.008;
    box.add(horizontalBand);

    const seal = new THREE.Mesh(
      new THREE.TorusGeometry(0.21, 0.047, 12, 36),
      ribbonEdge,
    );
    seal.rotation.x = -Math.PI / 2;
    seal.position.set(0, 0.66, 0.03);
    box.add(seal);

    const labelCanvas = document.createElement('canvas');
    labelCanvas.width = 512;
    labelCanvas.height = 256;
    const ctx = labelCanvas.getContext('2d');
    if (ctx) {
      ctx.fillStyle = '#fffdf7';
      ctx.fillRect(0, 0, labelCanvas.width, labelCanvas.height);
      ctx.fillStyle = '#174a35';
      ctx.fillRect(30, 31, 9, 194);
      ctx.font = '700 31px Arial, sans-serif';
      ctx.letterSpacing = '4px';
      ctx.fillText('RETAIL MIND', 68, 116);
      ctx.fillStyle = '#788477';
      ctx.font = '500 20px Arial, sans-serif';
      ctx.letterSpacing = '2px';
      ctx.fillText('A LITTLE CLOSER', 68, 160);
    }

    const labelTexture = new THREE.CanvasTexture(labelCanvas);
    labelTexture.colorSpace = THREE.SRGBColorSpace;
    const label = new THREE.Mesh(
      new THREE.PlaneGeometry(0.62, 0.31),
      new THREE.MeshStandardMaterial({ map: labelTexture, roughness: 0.85 }),
    );
    label.position.set(0.48, -0.08, 0.591);
    label.rotation.y = -0.12;
    box.add(label);

    const orbit = new THREE.Group();
    scene.add(orbit);
    const orbitLine = new THREE.Mesh(
      new THREE.TorusGeometry(1.45, 0.008, 6, 120),
      new THREE.MeshBasicMaterial({
        color: 0xd9ed9a,
        transparent: true,
        opacity: 0.58,
      }),
    );
    orbitLine.scale.set(1.08, 0.78, 1);
    orbitLine.rotation.set(1.12, -0.28, -0.2);
    orbit.add(orbitLine);

    const orbitDot = new THREE.Mesh(
      new THREE.SphereGeometry(0.065, 20, 14),
      new THREE.MeshStandardMaterial({
        color: 0xf1bd68,
        roughness: 0.28,
        metalness: 0.22,
      }),
    );
    orbit.add(orbitDot);

    const sparkleMaterial = new THREE.MeshBasicMaterial({
      color: 0xfff0c1,
      transparent: true,
      opacity: 0.85,
    });
    const sparkles = [
      new THREE.Mesh(new THREE.IcosahedronGeometry(0.035, 0), sparkleMaterial),
      new THREE.Mesh(new THREE.IcosahedronGeometry(0.025, 0), sparkleMaterial),
      new THREE.Mesh(new THREE.IcosahedronGeometry(0.03, 0), sparkleMaterial),
    ];
    sparkles[0].position.set(-1.22, 0.66, 0.2);
    sparkles[1].position.set(1.22, 0.62, -0.1);
    sparkles[2].position.set(-0.92, -0.72, 0.4);
    scene.add(...sparkles);

    const resize = () => {
      const { width, height } = host.getBoundingClientRect();
      if (!width || !height) return;
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.position.z = width < 360 ? 7 : 6.2;
      camera.updateProjectionMatrix();
    };

    let raf = 0;
    let running = false;
    let visible = true;
    let time = 0;
    let last = performance.now();

    const render = (now: number) => {
      const delta = Math.min((now - last) / 1000, 0.05);
      last = now;
      if (!still) time += delta;

      box.rotation.y = Math.sin(time * 0.42) * 0.36;
      box.rotation.x = Math.sin(time * 0.64) * 0.045;
      box.position.y = Math.sin(time * 0.9) * 0.085;
      orbit.rotation.y = time * 0.18;
      orbit.rotation.z = Math.sin(time * 0.23) * 0.04;
      orbitDot.position.set(
        Math.cos(time * 0.54) * 1.57,
        Math.sin(time * 0.54) * 0.9,
        Math.sin(time * 0.54) * 0.34,
      );
      sparkles.forEach((sparkle, index) => {
        sparkle.scale.setScalar(0.7 + (Math.sin(time * 1.2 + index * 1.7) + 1) * 0.18);
      });

      renderer.render(scene, camera);
      host.dataset.ready = 'true';
      if (running && !still) raf = requestAnimationFrame(render);
    };

    const start = () => {
      if (running || still) return;
      running = true;
      last = performance.now();
      raf = requestAnimationFrame(render);
    };

    const stop = () => {
      running = false;
      cancelAnimationFrame(raf);
    };

    const sync = () => {
      if (visible && !document.hidden && !still) start();
      else stop();
    };

    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      sync();
    });
    observer.observe(host);

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(host);
    resize();

    const onMotionPreferenceChange = (event: MediaQueryListEvent) => {
      still = event.matches;
      if (still) {
        stop();
        render(performance.now());
      } else {
        sync();
      }
    };
    reducedMotion.addEventListener('change', onMotionPreferenceChange);
    document.addEventListener('visibilitychange', sync);

    if (still) render(performance.now());
    else sync();

    return () => {
      stop();
      observer.disconnect();
      resizeObserver.disconnect();
      reducedMotion.removeEventListener('change', onMotionPreferenceChange);
      document.removeEventListener('visibilitychange', sync);
      scene.traverse((object) => {
        const renderable = object as THREE.Mesh;
        renderable.geometry?.dispose();
        if (Array.isArray(renderable.material)) {
          renderable.material.forEach((material) => material.dispose());
        } else {
          renderable.material?.dispose();
        }
      });
      labelTexture.dispose();
      renderer.dispose();
      renderer.domElement.remove();
      delete host.dataset.ready;
    };
  }, []);

  return (
    <div ref={hostRef} className="orders-fk-scene" aria-hidden="true">
      <span className="orders-fk-scene-fallback">
        <Package size={66} strokeWidth={1.1} />
      </span>
    </div>
  );
}
