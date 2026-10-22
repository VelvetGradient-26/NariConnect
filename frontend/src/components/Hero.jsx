import React, { Suspense } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Environment } from '@react-three/drei';
import NetworkAnimation from './NetworkAnimation';

const Hero = () => {
  const navigate = useNavigate();

  return (
    <section className="relative pt-20 pb-12 lg:pt-32 lg:pb-24 overflow-hidden bg-gradient-to-br from-rose-50 to-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          
          {/* Text Content */}
          <motion.div
            initial={{ opacity: 0, x: -50 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8 }}
          >
            <div className="inline-flex items-center px-3 py-1 rounded-full bg-rose-100 text-rose-600 text-sm font-medium mb-6">
              <span className="mr-2">✨</span> POWERED BY ADVANCED AI
            </div>
            
            <h1 className="text-5xl lg:text-7xl font-bold tracking-tight text-gray-900 leading-tight mb-6">
              Fund Your <span className="text-rose-500 italic">Ambition.</span><br />
              Build Your <span className="text-gray-900">Empire.</span>
            </h1>
            
            <p className="text-lg text-gray-600 mb-8 max-w-lg leading-relaxed">
              Stop searching, start scaling. Our intelligent AI instantly matches your unique business profile with 
              government & private financial schemes designed exclusively for women.
            </p>
            
            <div className="flex flex-col sm:flex-row gap-4">
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => navigate('/chat')}
                className="px-8 py-4 bg-rose-500 text-white rounded-xl font-semibold shadow-lg shadow-rose-500/30 hover:bg-rose-600 transition-all"
              >
                Start Matching
              </motion.button>
              
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => navigate('/schemes')}
                className="px-8 py-4 bg-white text-rose-600 border border-rose-100 rounded-xl font-semibold hover:bg-rose-50 transition-all"
              >
                Browse Schemes
              </motion.button>
            </div>
          </motion.div>

          {/* 3D Visual */}
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="relative h-[400px] lg:h-[600px] w-full"
          >
            <div className="absolute inset-0 bg-gradient-to-tr from-rose-100/50 to-transparent rounded-3xl -z-10 blur-3xl" />
            
            <Canvas camera={{ position: [0, 0, 8], fov: 45 }}>
              <Suspense fallback={null}>
                <ambientLight intensity={0.5} />
                <pointLight position={[10, 10, 10]} intensity={1} />
                <NetworkAnimation />
                <OrbitControls enableZoom={false} autoRotate autoRotateSpeed={0.5} />
                <Environment preset="city" />
              </Suspense>
            </Canvas>
          </motion.div>
        </div>
      </div>
    </section>
  );
};

export default Hero;
