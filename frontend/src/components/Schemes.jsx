import React from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { ArrowRight, BadgeCheck, BarChart, Utensils } from 'lucide-react';

const schemes = [
  {
    title: "Mudra Loan for Women",
    description: "Collateral-free loans up to 10 Lakhs with special interest rate concessions for small-scale businesses.",
    tag: "MOST POPULAR",
    category: "Small Business",
    icon: <BadgeCheck className="w-8 h-8 text-green-500" />,
    color: "bg-green-50 text-green-700",
  },
  {
    title: "Stand Up India",
    description: "Bank loans between 10 Lakhs and 1 Crore for setting up greenfield enterprises in manufacturing or services.",
    tag: "HIGH VOLUME",
    category: "Manufacturing",
    icon: <BarChart className="w-8 h-8 text-blue-500" />,
    color: "bg-blue-50 text-blue-700",
  },
  {
    title: "Annapurna Scheme",
    description: "Financial assistance for women to establish food catering units and buy kitchen equipment.",
    tag: "FOOD TECH",
    category: "Catering",
    icon: <Utensils className="w-8 h-8 text-orange-500" />,
    color: "bg-orange-50 text-orange-700",
  },
];

const Schemes = () => {
  return (
    <section id="schemes" className="py-20 bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-end mb-12">
          <div>
            <h2 className="text-4xl font-bold text-gray-900 mb-4">AI-Curated Financial Schemes</h2>
            <p className="text-gray-600 max-w-xl">
              Intelligently matched capital opportunities for early-stage and established women-led ventures.
            </p>
          </div>
          <Link to="/schemes" className="hidden md:flex items-center text-rose-500 font-semibold hover:text-rose-600 transition-colors">
            View all 50+ schemes <ArrowRight className="ml-2 w-5 h-5" />
          </Link>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
          {schemes.map((scheme, index) => (
            <motion.div
              key={index}
              whileHover={{ y: -10 }}
              className="bg-white rounded-2xl p-6 shadow-xl shadow-gray-200/50 hover:shadow-2xl transition-all border border-gray-100"
            >
              <div className="flex justify-between items-start mb-6">
                <span className={`px-3 py-1 rounded-full text-xs font-bold tracking-wide ${scheme.color}`}>
                  {scheme.tag}
                </span>
                <div className="p-2 bg-gray-50 rounded-full">
                  {scheme.icon}
                </div>
              </div>
              
              <h3 className="text-xl font-bold text-gray-900 mb-3">{scheme.title}</h3>
              <p className="text-gray-600 text-sm mb-6 leading-relaxed">
                {scheme.description}
              </p>
              
              <div className="flex gap-2">
                <span className="px-3 py-1 bg-gray-100 text-gray-600 text-xs rounded-md font-medium">
                  ZERO COLLATERAL
                </span>
                <span className="px-3 py-1 bg-gray-100 text-gray-600 text-xs rounded-md font-medium">
                  GOVT BACKED
                </span>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default Schemes;
