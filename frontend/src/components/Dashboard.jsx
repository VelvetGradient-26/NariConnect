import React from 'react';
import { UserButton, useUser } from '@clerk/clerk-react';
import { 
  LayoutDashboard, 
  Banknote, 
  FileText, 
  UserCircle, 
  Bell, 
  Settings, 
  Search,
  Filter,
  ArrowUpDown,
  Wallet,
  TrendingUp,
  GraduationCap,
  MessageSquare
} from 'lucide-react';

const Dashboard = () => {
  const { user } = useUser();

  const schemes = [
    {
      title: "Women in Tech Innovation Grant",
      description: "Up to ₹50,00,000 for female-led SaaS platforms.",
      match: 95,
      expires: "5 days",
      tag: "TOP MATCH",
      tagColor: "bg-rose-100 text-rose-600",
      progress: 95,
      icon: <LayoutDashboard className="w-6 h-6 text-rose-500" />
    },
    {
      title: "Sustainable Growth Micro-loan",
      description: "Low-interest funding for ethical business models.",
      match: 82,
      expires: "12 days",
      tag: "REGIONAL",
      tagColor: "bg-gray-100 text-gray-600",
      progress: 82,
      icon: <TrendingUp className="w-6 h-6 text-emerald-500" />
    }
  ];

  const allSchemes = [
    {
      title: "Angel Investment Network Grant",
      industry: "General",
      funding: "Equity-free",
      amount: "₹25,00,000",
      match: 78,
      icon: <Wallet className="w-6 h-6 text-rose-500" />
    },
    {
      title: "Scale-up Accelerator 2024",
      industry: "Tech",
      funding: "Mentorship + ₹15k",
      amount: "₹15,00,000",
      match: 65,
      icon: <TrendingUp className="w-6 h-6 text-rose-500" />
    },
    {
      title: "STEM Leadership Scholarship",
      industry: "Education/Tech",
      funding: "Training",
      amount: "N/A",
      match: 42,
      icon: <GraduationCap className="w-6 h-6 text-rose-500" />
    }
  ];

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Main Content */}
      <main className="flex-1 p-4 md:p-8">
        {/* Welcome Section */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Welcome back, {user?.firstName || "Founder"}</h1>
          <p className="text-gray-600 flex justify-between items-center">
            <span>We found 12 new financial schemes matching your tech startup profile.</span>
            <span className="text-sm text-gray-400 hidden sm:inline">October 24, 2023</span>
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
            <p className="text-gray-500 text-sm mb-1">Matched Schemes</p>
            <div className="flex items-baseline gap-2">
              <h3 className="text-3xl font-bold text-gray-900">12</h3>
              <span className="text-emerald-500 text-sm font-medium">+2 new</span>
            </div>
          </div>
          <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
            <p className="text-gray-500 text-sm mb-1">Active Applications</p>
            <div className="flex items-baseline gap-2">
              <h3 className="text-3xl font-bold text-gray-900">3</h3>
              <span className="text-gray-400 text-sm font-medium">no change</span>
            </div>
          </div>
          <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
            <p className="text-gray-500 text-sm mb-1">Funding Received</p>
            <div className="flex items-baseline gap-2">
              <h3 className="text-3xl font-bold text-gray-900">₹45,00,000</h3>
              <span className="text-emerald-500 text-sm font-medium">+₹5k</span>
            </div>
          </div>
        </div>

        {/* Recommended Section */}
        <div className="mb-8">
          <div className="flex justify-between items-center mb-4">
            <div className="flex items-center gap-2">
              <span className="text-rose-500 text-xl">✨</span>
              <h2 className="text-xl font-bold text-gray-900">Recommended for You</h2>
            </div>
            <a href="#" className="text-rose-500 text-sm font-medium hover:text-rose-600">View All</a>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            {schemes.map((scheme, index) => (
              <div key={index} className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex justify-between items-start mb-4">
                  <span className={`px-3 py-1 rounded-full text-xs font-bold ${scheme.tagColor}`}>
                    {scheme.tag}
                  </span>
                  <span className="text-xs text-gray-400 font-medium">Expires in {scheme.expires}</span>
                </div>
                
                <h3 className="text-lg font-bold text-gray-900 mb-2">{scheme.title}</h3>
                <p className="text-gray-600 text-sm mb-4">{scheme.description}</p>
                
                <div className="mb-6">
                  <div className="flex justify-between text-xs font-medium mb-1">
                    <span className="flex items-center gap-1 text-gray-700">
                      Eligibility: {scheme.match}% Match
                    </span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-2">
                    <div 
                      className="bg-rose-500 h-2 rounded-full" 
                      style={{ width: `${scheme.progress}%` }}
                    ></div>
                  </div>
                </div>

                <div className="flex gap-3">
                  <button className="flex-1 bg-rose-500 text-white py-2.5 rounded-xl font-semibold hover:bg-rose-600 transition-colors">
                    Quick Apply
                  </button>
                  <button className="p-2.5 border border-gray-200 rounded-xl text-gray-400 hover:text-rose-500 hover:border-rose-200 transition-colors">
                    <FileText size={20} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* All Matched Schemes List */}
        <div>
          <div className="flex justify-between items-center mb-4">
            <div className="flex items-center gap-2">
              <div className="bg-rose-100 p-1 rounded">
                <LayoutDashboard size={16} className="text-rose-500" />
              </div>
              <h2 className="text-xl font-bold text-gray-900">All Matched Schemes</h2>
            </div>
            <div className="flex gap-2">
              <button className="flex items-center gap-2 px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-sm font-medium text-gray-600 hover:border-rose-200">
                <Filter size={14} /> Filter
              </button>
              <button className="flex items-center gap-2 px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-sm font-medium text-gray-600 hover:border-rose-200">
                <ArrowUpDown size={14} /> Sort
              </button>
            </div>
          </div>

          <div className="space-y-4">
            {allSchemes.map((scheme, index) => (
              <div key={index} className="bg-white p-4 rounded-2xl border border-gray-100 flex flex-col md:flex-row items-center gap-4 hover:shadow-sm transition-shadow">
                <div className="p-3 bg-rose-50 rounded-xl">
                  {scheme.icon}
                </div>
                
                <div className="flex-1 text-center md:text-left">
                  <h4 className="font-bold text-gray-900">{scheme.title}</h4>
                  <p className="text-xs text-gray-500">
                    Industry: {scheme.industry} • Funding: {scheme.funding}
                  </p>
                </div>

                <div className="flex items-center gap-8 w-full md:w-auto justify-between md:justify-end">
                  <div className="text-center md:text-right">
                    <p className="text-xs text-gray-400 uppercase font-bold">Max Amount</p>
                    <p className="font-bold text-gray-900">{scheme.amount}</p>
                  </div>

                  <div className="flex items-center gap-3">
                    <div className="w-24 bg-gray-100 rounded-full h-1.5">
                      <div 
                        className="bg-rose-500 h-1.5 rounded-full" 
                        style={{ width: `${scheme.match}%` }}
                      ></div>
                    </div>
                    <span className="text-sm font-bold text-rose-500">{scheme.match}%</span>
                  </div>

                  <button className="px-4 py-2 bg-rose-50 text-rose-600 rounded-lg text-sm font-bold hover:bg-rose-100 transition-colors">
                    Details
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
};

export default Dashboard;
