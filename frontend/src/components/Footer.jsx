import React from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Heart } from 'lucide-react';

const Footer = () => {
  const navigate = useNavigate();

  return (
    <footer className="bg-white pt-24 pb-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* CTA Section */}
        <motion.div 
          initial={{ scale: 0.95, opacity: 0 }}
          whileInView={{ scale: 1, opacity: 1 }}
          viewport={{ once: true }}
          className="bg-gradient-to-r from-rose-500 to-pink-600 rounded-3xl p-12 text-center text-white mb-20 shadow-2xl shadow-rose-500/30 relative overflow-hidden"
        >
          <div className="absolute top-0 left-0 w-full h-full bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] opacity-10"></div>
          
          <h2 className="text-3xl md:text-5xl font-bold mb-6 relative z-10">
            Ready to transform your <br/> business?
          </h2>
          <p className="text-rose-100 text-lg mb-8 max-w-2xl mx-auto relative z-10">
            Join thousands of women entrepreneurs who secured funding through NariConnect this year.
          </p>
          
          <div className="flex flex-col sm:flex-row gap-4 justify-center relative z-10">
            <button
              onClick={() => navigate('/chat')}
              className="bg-white text-rose-600 px-8 py-4 rounded-xl font-bold hover:bg-gray-100 transition-colors shadow-lg">
              Apply for AI Matching
            </button>
          </div>
        </motion.div>

        {/* Footer Links */}
        <div className="flex flex-col md:flex-row justify-between items-center pt-8 border-t border-gray-100">
          <div className="flex items-center space-x-2 mb-4 md:mb-0">
            <div className="w-8 h-8 bg-rose-500 rounded-lg flex items-center justify-center">
              <Heart className="w-4 h-4 text-white fill-current" />
            </div>
            <span className="font-bold text-gray-900 text-lg">NariConnect</span>
          </div>
          
          <div className="flex space-x-8 text-sm text-gray-500">
            <a href="#" className="hover:text-rose-500 transition-colors">Privacy</a>
            <a href="#" className="hover:text-rose-500 transition-colors">Terms</a>
            <a href="#" className="hover:text-rose-500 transition-colors">Cookie Policy</a>
          </div>
          
          <div className="text-sm text-gray-400 mt-4 md:mt-0">
            © 2026 NariConnect Platform. Built for SheLeads.
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
