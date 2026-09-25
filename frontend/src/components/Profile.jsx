import React, { useState } from 'react';
import { useUser } from '@clerk/clerk-react';
import { motion } from 'framer-motion';
import { Save, ArrowLeft, LayoutDashboard } from 'lucide-react';

const STATES = [
  "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", 
  "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", 
  "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", 
  "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", 
  "Uttarakhand", "West Bengal", "Andaman and Nicobar Islands", "Chandigarh", 
  "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Jammu and Kashmir", "Ladakh", 
  "Lakshadweep", "Puducherry"
];

const CATEGORIES = [
  "General", "Other Backward Class (OBC)", "Scheduled Caste (SC)", 
  "Scheduled Tribe (ST)", "Nomadic or Semi-Nomadic Communities"
];

const loadSavedProfile = () => {
  try {
    return JSON.parse(localStorage.getItem('userProfile')) || {};
  } catch {
    return {};
  }
};

const Profile = () => {
  const { user } = useUser();
  const [formData, setFormData] = useState(() => ({
    firstName: user?.firstName || '',
    lastName: user?.lastName || '',
    email: user?.primaryEmailAddress?.emailAddress || '',
    dob: '',
    age: '',
    maritalStatus: '',
    state: '',
    areaOfResidence: '',
    category: '',
    isDisabled: '',
    isMinority: '',
    isStudent: '',
    employmentStatus: '',
    isBPL: '',
    annualIncome: '',
    isDistress: '',
    ...loadSavedProfile()
  }));
  const [isSaved, setIsSaved] = useState(false);

  const calculateAge = (dob) => {
    const today = new Date();
    const birthDate = new Date(dob);
    let age = today.getFullYear() - birthDate.getFullYear();
    const m = today.getMonth() - birthDate.getMonth();
    if (m < 0 || (m === 0 && today.getDate() < birthDate.getDate())) {
      age--;
    }
    return age;
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => {
      const newData = { ...prev, [name]: value };
      if (name === 'dob') {
        newData.age = calculateAge(value);
      }
      return newData;
    });
    setIsSaved(false);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    localStorage.setItem('userProfile', JSON.stringify(formData));
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 3000);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 py-8">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-3xl shadow-sm border border-gray-100 overflow-hidden"
        >
          <div className="p-8 border-b border-gray-100 bg-gradient-to-r from-rose-50 to-white">
            <div className="flex items-center gap-6">
              <div className="w-24 h-24 rounded-full border-4 border-white shadow-lg overflow-hidden">
                <img src={user?.imageUrl} alt="Profile" className="w-full h-full object-cover" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">{user?.fullName || "User"}</h1>
                <p className="text-sm text-gray-500 mt-1">{user?.primaryEmailAddress?.emailAddress}</p>
              </div>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="p-8 space-y-8">
            <div className="grid md:grid-cols-2 gap-8">
              {/* Personal Details */}
              <div className="space-y-6">
                <h3 className="text-lg font-bold text-gray-900 border-b border-gray-100 pb-2">Personal Details</h3>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">First Name</label>
                  <input
                    type="text"
                    name="firstName"
                    value={formData.firstName}
                    onChange={handleChange}
                    className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-rose-500 focus:border-rose-500 outline-none transition-all"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Last Name</label>
                  <input
                    type="text"
                    name="lastName"
                    value={formData.lastName}
                    onChange={handleChange}
                    className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-rose-500 focus:border-rose-500 outline-none transition-all"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Email</label>
                  <input
                    type="email"
                    name="email"
                    value={formData.email}
                    disabled
                    className="w-full px-4 py-3 rounded-xl border border-gray-200 bg-gray-50 text-gray-500 cursor-not-allowed"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Date of Birth</label>
                  <input
                    type="date"
                    name="dob"
                    value={formData.dob}
                    onChange={handleChange}
                    className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-rose-500 focus:border-rose-500 outline-none transition-all"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Age</label>
                  <input
                    type="number"
                    name="age"
                    value={formData.age}
                    readOnly
                    className="w-full px-4 py-3 rounded-xl border border-gray-200 bg-gray-50 focus:ring-2 focus:ring-rose-500 focus:border-rose-500 outline-none transition-all"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Marital Status</label>
                  <select
                    name="maritalStatus"
                    value={formData.maritalStatus}
                    onChange={handleChange}
                    className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-rose-500 focus:border-rose-500 outline-none transition-all"
                  >
                    <option value="">Select Status</option>
                    <option value="Single">Single</option>
                    <option value="Married">Married</option>
                    <option value="Widowed">Widowed</option>
                    <option value="Divorced">Divorced</option>
                    <option value="Separated">Separated</option>
                  </select>
                </div>
              </div>

              {/* Location & Category */}
              <div className="space-y-6">
                <h3 className="text-lg font-bold text-gray-900 border-b border-gray-100 pb-2">Location & Category</h3>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">State</label>
                  <select
                    name="state"
                    value={formData.state}
                    onChange={handleChange}
                    className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-rose-500 focus:border-rose-500 outline-none transition-all"
                  >
                    <option value="">Select State</option>
                    {STATES.map(state => (
                      <option key={state} value={state}>{state}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Category</label>
                  <select
                    name="category"
                    value={formData.category}
                    onChange={handleChange}
                    className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-rose-500 focus:border-rose-500 outline-none transition-all"
                  >
                    <option value="">Select Category</option>
                    {CATEGORIES.map(cat => (
                      <option key={cat} value={cat}>{cat}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Area of Residence</label>
                  <div className="flex gap-4">
                    {['Urban', 'Rural'].map((area) => (
                      <label key={area} className="flex-1 cursor-pointer">
                        <input
                          type="radio"
                          name="areaOfResidence"
                          value={area}
                          checked={formData.areaOfResidence === area}
                          onChange={handleChange}
                          className="peer sr-only"
                        />
                        <div className="text-center py-3 rounded-xl border border-gray-200 peer-checked:bg-rose-500 peer-checked:text-white peer-checked:border-rose-500 transition-all">
                          {area}
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Additional Info */}
            <div className="space-y-6">
              <h3 className="text-lg font-bold text-gray-900 border-b border-gray-100 pb-2">Additional Information</h3>
              <div className="grid md:grid-cols-2 gap-6">
                <YesNoQuestion 
                  label="Person with Disability" 
                  name="isDisabled" 
                  value={formData.isDisabled}
                  onChange={handleChange} 
                />
                <YesNoQuestion 
                  label="Minority Community" 
                  name="isMinority" 
                  value={formData.isMinority}
                  onChange={handleChange} 
                />
                <YesNoQuestion 
                  label="Student Status" 
                  name="isStudent" 
                  value={formData.isStudent}
                  onChange={handleChange} 
                />
              </div>

              {/* Conditional Employment Status */}
              {formData.isStudent === 'No' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Employment Status</label>
                  <select
                    name="employmentStatus"
                    value={formData.employmentStatus}
                    onChange={handleChange}
                    className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-rose-500 focus:border-rose-500 outline-none transition-all"
                  >
                    <option value="">Select Employment Status</option>
                    <option value="Unemployed">Unemployed</option>
                    <option value="Employed">Employed</option>
                    <option value="Self Employed">Self Employed</option>
                    <option value="Entrepreneur">Entrepreneur</option>
                  </select>
                </div>
              )}

              <div className="grid md:grid-cols-2 gap-6">
                <YesNoQuestion 
                  label="Below Poverty Line (BPL)" 
                  name="isBPL" 
                  value={formData.isBPL}
                  onChange={handleChange} 
                />
                
                {/* Conditional Annual Income */}
                {formData.isBPL === 'No' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Family's Annual Income</label>
                    <input
                      type="number"
                      name="annualIncome"
                      value={formData.annualIncome}
                      onChange={handleChange}
                      placeholder="Enter annual income"
                      className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-2 focus:ring-rose-500 focus:border-rose-500 outline-none transition-all"
                    />
                  </div>
                )}
              </div>
              
              {/* Conditional Distress */}
              {formData.isBPL === 'Yes' && (
                <div className="bg-rose-50 p-6 rounded-2xl">
                  <YesNoQuestion 
                    label="Are you in any condition of extreme hardship? (Destitute / Penury / Distress)" 
                    name="isDistress" 
                    value={formData.isDistress}
                    onChange={handleChange} 
                    fullWidth
                  />
                </div>
              )}
            </div>

            <div className="flex justify-end pt-4">
              <button
                type="submit"
                className="flex items-center gap-2 bg-rose-500 text-white px-8 py-3 rounded-xl font-bold hover:bg-rose-600 transition-colors shadow-lg shadow-rose-500/30"
              >
                <Save size={20} />
                {isSaved ? 'Saved Successfully!' : 'Save Changes'}
              </button>
            </div>
          </form>
        </motion.div>
      </div>
    </div>
  );
};

const YesNoQuestion = ({ label, name, value, onChange, fullWidth }) => (
  <div className={fullWidth ? "w-full" : ""}>
    <label className="block text-sm font-medium text-gray-700 mb-2">{label}</label>
    <div className="flex gap-4">
      {['Yes', 'No'].map((option) => (
        <label key={option} className="flex-1 cursor-pointer">
          <input
            type="radio"
            name={name}
            value={option}
            checked={value === option}
            onChange={onChange}
            className="peer sr-only"
          />
          <div className="text-center py-2.5 rounded-xl border border-gray-200 peer-checked:bg-rose-100 peer-checked:text-rose-700 peer-checked:border-rose-200 hover:bg-gray-50 transition-all text-sm font-medium">
            {option}
          </div>
        </label>
      ))}
    </div>
  </div>
);

export default Profile;
