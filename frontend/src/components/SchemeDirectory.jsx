import React, { useState, useEffect } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { useNavigate } from 'react-router-dom';
import { 
  Search, 
  Filter, 
  X, 
  ChevronLeft, 
  ChevronRight,
  Building2,
  Bookmark,
  ArrowRight,
  School,
  Heart,
  Wheat,
  Briefcase,
  Users
} from 'lucide-react';
import { fetchSchemes } from '../services/api';

const SchemeDirectory = () => {
  const { getToken } = useAuth();
  const navigate = useNavigate();

  const [schemes, setSchemes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalSchemes, setTotalSchemes] = useState(0);
  
  const [filters, setFilters] = useState({
    search: '',
    sector: '',
    state: '',
    level: ''
  });

  const [activeFilters, setActiveFilters] = useState([]);

  // Reload when page or filters change
  useEffect(() => {
    // Typing in search fires a request per keystroke; ignore responses that arrive out of order
    let stale = false;

    const loadSchemes = async () => {
      setLoading(true);
      try {
        const token = await getToken();
        const data = await fetchSchemes(token, page, filters);
        if (stale) return;
        setSchemes(data.data);
        setTotalPages(data.total_pages);
        setTotalSchemes(data.total);
      } catch (error) {
        if (!stale) console.error("Failed to load schemes", error);
      } finally {
        if (!stale) setLoading(false);
      }
    };

    loadSchemes();
    return () => {
      stale = true;
    };
  }, [page, filters, getToken]);

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    setPage(1); // Reset to page 1 on filter change
    
    // Update active filters display
    if (value && value !== 'All Stages' && value !== '') {
      if (!activeFilters.find(f => f.key === key)) {
        setActiveFilters(prev => [...prev, { key, value }]);
      } else {
        setActiveFilters(prev => prev.map(f => f.key === key ? { key, value } : f));
      }
    } else {
      setActiveFilters(prev => prev.filter(f => f.key !== key));
    }
  };

  const removeFilter = (key) => {
    setFilters(prev => ({ ...prev, [key]: '' }));
    setPage(1);
    setActiveFilters(prev => prev.filter(f => f.key !== key));
  };

  // Helper function to get appropriate icon for scheme category
  const getSchemeIcon = (category) => {
    if (!category || !category[0]?.label) return Briefcase;
    
    const label = category[0].label.toLowerCase();
    if (label.includes('education')) return School;
    if (label.includes('health')) return Heart;
    if (label.includes('agriculture')) return Wheat;
    if (label.includes('business')) return Briefcase;
    if (label.includes('social')) return Users;
    return Briefcase;
  };

  return (
    <div className="bg-white font-['Manrope'] text-slate-900 min-h-screen flex flex-col">
      
      {/* Main Content */}
      <main className="max-w-7xl mx-auto w-full flex flex-col lg:flex-row gap-8 px-6 lg:px-20 py-10 flex-1">
        
        {/* Sidebar Filters */}
        <aside className="w-full lg:w-72 shrink-0 flex flex-col gap-8">
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-bold text-lg flex items-center gap-2 text-slate-800">
                <Filter className="text-rose-500" size={24} />
                Filters
              </h3>
              <button 
                onClick={() => {
                  setFilters({ search: '', sector: '', state: '', level: '' });
                  setActiveFilters([]);
                  setPage(1);
                }}
                className="text-xs font-semibold text-rose-500 hover:underline"
              >
                Reset All
              </button>
            </div>
            
            <div className="space-y-8">
              {/* Sector Filter */}
              <div className="space-y-3">
                <label className="text-sm font-bold text-slate-500 uppercase tracking-wider">Sector</label>
                <div className="flex flex-col gap-2">
                  {['Agriculture', 'Education', 'Business', 'Healthcare', 'Social Welfare'].map(sector => (
                    <label key={sector} className="flex items-center gap-3 cursor-pointer group">
                      <input 
                        type="radio" 
                        name="sector"
                        checked={filters.sector === sector}
                        onChange={() => handleFilterChange('sector', sector)}
                        className="rounded border-slate-300 text-rose-500 focus:ring-rose-500/20 h-5 w-5 accent-rose-500" 
                      />
                      <span className="text-sm text-slate-600 group-hover:text-rose-500 transition-colors">{sector}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Level Filter */}
              <div className="space-y-3">
                <label className="text-sm font-bold text-slate-500 uppercase tracking-wider">Level</label>
                <select 
                  className="w-full rounded-lg border-slate-200 bg-white focus:border-rose-500 focus:ring-rose-500 text-sm p-2 outline-none"
                  value={filters.level}
                  onChange={(e) => handleFilterChange('level', e.target.value)}
                >
                  <option value="">All Levels</option>
                  <option value="Central">Central</option>
                  <option value="State">State</option>
                </select>
              </div>

              {/* Quick Select Tags */}
              <div className="space-y-3">
                <label className="text-sm font-bold text-slate-500 uppercase tracking-wider">Quick Select</label>
                <div className="flex flex-wrap gap-2">
                  <span onClick={() => handleFilterChange('search', 'Women')} className="px-3 py-1 bg-rose-500 text-white text-[10px] font-bold rounded-full cursor-pointer hover:bg-rose-600 transition-colors">Women Led</span>
                  <span onClick={() => handleFilterChange('search', 'Student')} className="px-3 py-1 bg-rose-50 text-rose-600 border border-rose-100 text-[10px] font-bold rounded-full hover:bg-rose-100 transition-colors cursor-pointer">Students</span>
                  <span onClick={() => handleFilterChange('search', 'Rural')} className="px-3 py-1 bg-rose-50 text-rose-600 border border-rose-100 text-[10px] font-bold rounded-full hover:bg-rose-100 transition-colors cursor-pointer">Rural Area</span>
                </div>
              </div>
            </div>
          </div>
        </aside>

        {/* Main Scheme List */}
        <section className="flex-1 space-y-6">
          
          {/* Header Info */}
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
              <h1 className="text-3xl font-black tracking-tight mb-1 text-slate-900">Scheme Directory</h1>
              <p className="text-slate-500">Discover {totalSchemes} active government assistance programs.</p>
            </div>
            
            {/* Search Bar */}
            <div className="flex items-center bg-white border border-slate-200 rounded-lg px-3 py-2 w-full md:w-64 focus-within:ring-2 focus-within:ring-rose-500/20 focus-within:border-rose-500 transition-all">
              <Search className="text-slate-400" size={20} />
              <input 
                className="bg-transparent border-none focus:outline-none text-sm w-full placeholder-slate-400 text-slate-700 ml-2" 
                placeholder="Search schemes..." 
                type="text"
                value={filters.search}
                onChange={(e) => handleFilterChange('search', e.target.value)}
              />
            </div>
          </div>

          {/* Active Filter Tags */}
          {activeFilters.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {activeFilters.map((filter, idx) => (
                <div key={idx} className="flex items-center gap-2 bg-white border border-slate-200 px-3 py-1.5 rounded-lg text-sm">
                  <span className="text-slate-500 capitalize">{filter.key}:</span>
                  <span className="font-semibold text-slate-700">{filter.value}</span>
                  <span 
                    onClick={() => removeFilter(filter.key)}
                    className="text-sm cursor-pointer hover:text-rose-500 text-slate-400"
                  >
                    <X size={16} />
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Loading State */}
          {loading ? (
            <div className="flex justify-center py-20">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-rose-500"></div>
            </div>
          ) : (
            /* Scheme List */
            <div className="grid gap-6">
              {schemes.map((scheme) => (
                <div key={scheme.slug} className="bg-white border border-slate-200 rounded-xl p-6 hover:shadow-xl hover:shadow-rose-500/5 transition-all flex flex-col md:flex-row gap-6 group">
                  <div className="size-16 rounded-xl bg-rose-50 flex items-center justify-center text-rose-500 shrink-0 group-hover:scale-110 transition-transform">
                    {(() => {
                      const IconComponent = getSchemeIcon(scheme.basicDetails?.schemeCategory);
                      return <IconComponent size={32} className="text-rose-500" />;
                    })()}
                  </div>
                  
                  <div className="flex-1">
                    <div className="flex justify-between items-start mb-2">
                      <h3 className="text-xl font-bold text-slate-800 group-hover:text-rose-500 transition-colors">
                        {scheme.basicDetails?.schemeName}
                      </h3>
                      <span className="bg-emerald-50 text-emerald-600 text-[10px] font-black uppercase px-2 py-1 rounded border border-emerald-100">
                        Active
                      </span>
                    </div>
                    
                    <p className="text-slate-500 text-sm mb-4 line-clamp-2 leading-relaxed">
                      {scheme.schemeContent?.briefDescription}
                    </p>
                    
                    <div className="flex flex-wrap gap-2 mb-6">
                      {scheme.basicDetails?.schemeCategory?.slice(0, 3).map((cat, i) => (
                         <span key={i} className="px-2.5 py-1 bg-slate-50 border border-slate-200 rounded-md text-xs font-semibold text-slate-600">
                           {cat.label || cat}
                         </span>
                      ))}
                      <span className="px-2.5 py-1 bg-slate-50 border border-slate-200 rounded-md text-xs font-semibold text-slate-600">
                        {scheme.basicDetails?.level?.label}
                      </span>
                    </div>
                    
                    <div className="flex items-center justify-between mt-auto pt-4 border-t border-slate-100">
                      <div className="flex items-center gap-4">
                         <span className="text-[10px] text-slate-400 uppercase tracking-wide font-bold flex items-center gap-1">
                           <Building2 size={14} className="text-slate-400" />
                           {scheme.basicDetails?.nodalMinistryName?.label}
                         </span>
                      </div>
                      
                      <div className="flex gap-2">
                        <button className="px-4 py-2 border border-slate-200 text-slate-600 rounded-lg text-sm font-bold hover:bg-slate-50 transition-colors flex items-center gap-2">
                          <Bookmark size={18} className="text-slate-400" />
                          Save
                        </button>
                        <button 
                          onClick={() => navigate(`/schemes/${scheme.slug}`)}
                          className="px-4 py-2 bg-rose-500 text-white rounded-lg text-sm font-bold hover:bg-rose-600 transition-all flex items-center gap-2 shadow-lg shadow-rose-500/20"
                        >
                          View Details
                          <ArrowRight size={18} className="text-white" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Pagination */}
          <div className="flex items-center justify-center gap-2 py-8">
            <button 
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="size-10 flex items-center justify-center rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-400 disabled:opacity-50 transition-colors"
            >
              <ChevronLeft size={20} />
            </button>
            
            <span className="px-4 text-sm font-bold text-slate-600">
              Page {page} of {totalPages}
            </span>

            <button 
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="size-10 flex items-center justify-center rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-400 disabled:opacity-50 transition-colors"
            >
              <ChevronRight size={20} />
            </button>
          </div>

        </section>
      </main>
    </div>
  );
};

export default SchemeDirectory;
