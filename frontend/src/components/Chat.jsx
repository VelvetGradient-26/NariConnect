import React, { useState, useRef, useEffect } from 'react';
import { useUser, useAuth } from '@clerk/clerk-react';
import { 
  Send, 
  Paperclip, 
  Mic, 
  Bot, 
  LayoutDashboard,
  Bell,
  Share2,
  Loader2
} from 'lucide-react';
import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { chatWithAI } from '../services/api';

const Chat = () => {
  const { user } = useUser();
  const { getToken } = useAuth();
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [userProfile, setUserProfile] = useState({});
  const messagesEndRef = useRef(null);

  const [messages, setMessages] = useState([
    {
      id: 1,
      sender: 'bot',
      text: "Hello! I'm NariConnect AI. I can help you find financial schemes tailored to your profile. How can I assist you today?"
    }
  ]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;
    
    const userMessageText = input;
    const userMessage = { id: Date.now(), sender: 'user', text: userMessageText };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    // Prepare chat history
    const chatHistory = messages.map(msg => ({
      role: msg.sender === 'user' ? 'user' : 'assistant',
      content: msg.text
    }));

    try {
      const token = await getToken();
      const data = await chatWithAI(userMessageText, token, chatHistory, userProfile);
      
      if (data.user_profile) {
        setUserProfile(data.user_profile);
      }
      
      const botMessage = {
        id: Date.now() + 1,
        sender: 'bot',
        text: data.response,
        cards: data.schemes?.map(scheme => ({
          title: scheme.metadata.schemeShortTitle || scheme.metadata.schemeName,
          desc: scheme.metadata.description ? scheme.metadata.description.substring(0, 120) + "..." : "No description available",
          tag: scheme.metadata.categories?.split(',')[0] || "SCHEME"
        }))
      };
      
      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      console.error("Chat error:", error);
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        sender: 'bot',
        text: "I'm sorry, I encountered an error while processing your request. Please try again later."
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-64px)] bg-white overflow-hidden">
      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col bg-gray-50 relative">
        {/* Header */}
        <header className="bg-white border-b border-gray-100 px-6 py-4 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Bot className="text-rose-500" />
            <span className="font-bold text-gray-900">NariConnect AI</span>
            <span className="bg-rose-100 text-rose-600 text-[10px] font-bold px-2 py-0.5 rounded-full">BETA</span>
          </div>
          <div className="flex items-center gap-4 text-gray-400">
            <Bell size={20} className="hover:text-gray-600 cursor-pointer" />
            <Share2 size={20} className="hover:text-gray-600 cursor-pointer" />
          </div>
        </header>

        {/* Chat Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-8">
          <div className="text-center my-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">Ask me anything about financial schemes</h1>
            <p className="text-gray-500">Personalized financial advice for the modern woman entrepreneur.</p>
          </div>

          {messages.map((msg) => (
            <motion.div 
              key={msg.id} 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex gap-4 ${msg.sender === 'user' ? 'flex-row-reverse' : ''}`}
            >
              <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${msg.sender === 'user' ? 'bg-rose-100' : 'bg-rose-500'}`}>
                {msg.sender === 'user' ? (
                  <img src={user?.imageUrl} alt="User" className="w-full h-full rounded-full object-cover" />
                ) : (
                  <Bot className="text-white w-6 h-6" />
                )}
              </div>
              
              <div className={`max-w-2xl space-y-4 ${msg.sender === 'user' ? 'items-end flex flex-col' : ''}`}>
                <div className={`p-6 rounded-2xl shadow-sm ${msg.sender === 'user' ? 'bg-rose-500 text-white rounded-tr-none' : 'bg-white text-gray-700 rounded-tl-none'}`}>
                  {msg.sender === 'user' ? (
                    <p className="leading-relaxed whitespace-pre-wrap">{msg.text}</p>
                  ) : (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ duration: 0.5 }}
                      className="markdown-content prose prose-sm max-w-none prose-p:leading-relaxed prose-headings:font-bold prose-a:text-rose-600 prose-strong:text-gray-900"
                    >
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.text}
                      </ReactMarkdown>
                    </motion.div>
                  )}
                </div>

                {msg.cards && msg.cards.length > 0 && (
                  <div className="grid md:grid-cols-2 gap-4 w-full">
                    {msg.cards.map((card, idx) => (
                      <div key={idx} className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm hover:shadow-md transition-shadow cursor-pointer">
                        <div className="flex justify-between items-start mb-3">
                          <div className="p-2 bg-rose-50 rounded-lg text-rose-500">
                            <LayoutDashboard size={20} />
                          </div>
                          <span className="text-[10px] font-bold bg-rose-100 text-rose-600 px-2 py-1 rounded-full truncate max-w-[120px]">{card.tag}</span>
                        </div>
                        <h4 className="font-bold text-gray-900 mb-2 line-clamp-2">{card.title}</h4>
                        <p className="text-sm text-gray-500 line-clamp-3">{card.desc}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </motion.div>
          ))}
          
          {isLoading && (
            <motion.div 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex gap-4"
            >
              <div className="w-10 h-10 rounded-full bg-rose-500 flex items-center justify-center flex-shrink-0">
                <Bot className="text-white w-6 h-6" />
              </div>
              <div className="p-6 rounded-2xl shadow-sm bg-white text-gray-700 rounded-tl-none flex items-center gap-2">
                <Loader2 className="w-5 h-5 animate-spin text-rose-500" />
                <span className="text-gray-500">Thinking...</span>
              </div>
            </motion.div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-6 bg-white border-t border-gray-100">
          <div className="max-w-4xl mx-auto relative">
            <div className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 cursor-pointer">
              <Paperclip size={20} />
            </div>
            
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Type your message about financial schemes..."
              disabled={isLoading}
              className="w-full pl-12 pr-24 py-4 bg-white border border-gray-200 rounded-2xl shadow-sm focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-transparent placeholder-gray-400 disabled:opacity-50 disabled:cursor-not-allowed"
            />
            
            <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-2">
              <button className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-full transition-colors">
                <Mic size={20} />
              </button>
              <button 
                onClick={handleSend}
                disabled={isLoading || !input.trim()}
                className="p-2 bg-rose-500 text-white rounded-xl hover:bg-rose-600 transition-colors shadow-md shadow-rose-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Send size={20} />
              </button>
            </div>
          </div>
          <p className="text-center text-[10px] text-gray-400 mt-3 font-medium tracking-wide uppercase">
            NariConnect AI can provide guidance but is not a substitute for professional legal or financial advice.
          </p>
        </div>
      </main>
    </div>
  );
};

export default Chat;
