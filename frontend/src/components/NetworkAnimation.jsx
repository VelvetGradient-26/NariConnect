import React, { useRef, useState } from 'react';
import { useFrame } from '@react-three/fiber';
import { Sphere, Line } from '@react-three/drei';
import * as THREE from 'three';

const NetworkAnimation = () => {
  const groupRef = useRef();

  useFrame((state) => {
    const time = state.clock.getElapsedTime();
    if (groupRef.current) {
      groupRef.current.rotation.y = time * 0.1;
      groupRef.current.rotation.x = Math.sin(time * 0.2) * 0.05;
    }
  });

  const count = 20;
  // Lazy state initializer: random layout is generated once per mount, outside render
  const [{ points, connections }] = useState(() => {
    const pts = new Array(count).fill(0).map(() => ({
      position: [
        (Math.random() - 0.5) * 8,
        (Math.random() - 0.5) * 8,
        (Math.random() - 0.5) * 8,
      ],
      size: Math.random() * 0.15 + 0.05,
    }));

    const conns = [];
    pts.forEach((pt, i) => {
      pts.slice(i + 1).forEach((otherPt) => {
        const dist = new THREE.Vector3(...pt.position).distanceTo(new THREE.Vector3(...otherPt.position));
        if (dist < 3.5) {
          conns.push([pt.position, otherPt.position]);
        }
      });
    });
    return { points: pts, connections: conns };
  });

  return (
    <group ref={groupRef}>
      {points.map((point, i) => (
        <Sphere key={i} args={[point.size, 16, 16]} position={point.position}>
          <meshStandardMaterial color="#f43f5e" emissive="#f43f5e" emissiveIntensity={0.8} roughness={0.2} />
        </Sphere>
      ))}
      {connections.map((conn, i) => (
        <Line
          key={i}
          points={conn}
          color="#db2777"
          lineWidth={1}
          transparent
          opacity={0.3}
        />
      ))}
    </group>
  );
};

export default NetworkAnimation;
