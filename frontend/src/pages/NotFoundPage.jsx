import React from 'react';
import { Link } from 'react-router-dom';
import Layout from '../components/Layout';

const NotFoundPage = () => {
  return (
    <Layout>
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center space-y-8 animate-[fadeIn_0.5s_ease-out]">

        {/* Glitchy 404 Text */}
        <h1 className="text-9xl font-black text-[#00E5FF] drop-shadow-[0_0_20px_rgba(0,229,255,0.5)] tracking-tighter">
            404
        </h1>

        <div className="space-y-2">
            <p className="text-[#E0F7FA] text-2xl font-bold uppercase tracking-widest">
                Block Not Found
            </p>
            <p className="text-[#9D4EDD] text-lg max-w-md mx-auto">
                The chain you are attempting to access does not exist or has been pruned from the ledger.
            </p>
        </div>

        {/* Cyber Button */}
        <Link
            to="/"
            className="group relative px-8 py-3 bg-[#00E5FF]/10 border border-[#00E5FF] text-[#00E5FF] font-bold uppercase tracking-wider rounded hover:bg-[#00E5FF] hover:text-[#050511] transition-all duration-300"
        >
            Return to Mainnet
            {/* Hover Glow Effect */}
            <div className="absolute inset-0 bg-[#00E5FF] blur-lg opacity-0 group-hover:opacity-40 transition-opacity"></div>
        </Link>
      </div>
    </Layout>
  );
};

export default NotFoundPage;