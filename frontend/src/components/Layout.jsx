import React from 'react';
import { Link } from 'react-router-dom';

const Layout = ({ children }) => {
  return (
    <div className="min-h-screen flex flex-col bg-[#050511] text-[#E0F7FA] font-sans selection:bg-[#00E5FF] selection:text-[#050511]">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b border-[#00E5FF]/20 bg-[#050511]/95 backdrop-blur-md px-6 py-4 lg:px-20 shadow-[0_4px_30px_rgba(0,229,255,0.05)]">
        <div className="flex items-center justify-between mx-auto max-w-7xl">

          {/* Logo & Brand Name */}
          <Link to="/" className="flex items-center gap-3 group">
            {/* --- IMAGE ADDED HERE --- */}
            {/* Ensure your file is named 'logo.png' and is in the 'public' folder */}
            <img
              src="/logo.png"
              alt="VoteChain Logo"
              className="h-10 w-10 object-contain drop-shadow-[0_0_8px_rgba(0,229,255,0.5)] group-hover:scale-110 transition-transform"
            />

            <h2 className="text-[#E0F7FA] text-xl font-bold tracking-tight">VoteChain</h2>
          </Link>

          <nav className="flex items-center gap-6">
             <Link to="/" className="text-[#9D4EDD] hover:text-[#00E5FF] transition-colors text-sm font-medium">Elections</Link>
             <Link to="/help" className="text-[#9D4EDD] hover:text-[#00E5FF] transition-colors text-sm font-medium">Help</Link>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 w-full">
        {children}
      </main>

      {/* Footer */}
      <footer className="mt-auto border-t border-[#9D4EDD]/20 bg-[#0a0a18] py-8 text-center text-[#9D4EDD] text-sm">
        <p>© 2025 VoteChain. View-Only Access Terminal.</p>
      </footer>
    </div>
  );
};

export default Layout;