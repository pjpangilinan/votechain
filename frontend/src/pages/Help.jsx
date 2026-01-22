import React from 'react';
import Layout from '../components/Layout'; // 1. Import the shared Layout

const HelpPage = () => {
  return (
    // 2. Wrap everything in Layout. This handles the Navbar and Footer automatically.
    <Layout>
      <div className="px-6 lg:px-20 py-12 max-w-[1600px] mx-auto">
        <div className="max-w-3xl mx-auto space-y-12">

          {/* Intro */}
          <div className="space-y-4 text-center">
            <h1 className="text-4xl font-bold text-[#E0F7FA]">Platform Guide</h1>
          </div>

          {/* Steps */}
          <div className="grid gap-6">

            {/* Step 1 */}
            <div className="p-6 rounded-xl bg-[#0a0a18] border border-[#9D4EDD]/20 hover:border-[#00E5FF]/50 transition-colors">
              <h3 className="text-xl font-bold text-[#00E5FF] mb-3 flex items-center gap-2">
                <span className="flex items-center justify-center w-6 h-6 rounded-full bg-[#00E5FF]/10 text-[#00E5FF] text-xs">1</span>
                Browsing Elections
              </h3>
              <p className="text-[#E0F7FA]/80 leading-relaxed pl-8">
                The home page displays all elections recorded on the chain.
                <span className="text-[#00E5FF]"> Active</span> elections are highlighted with live indicators, while
                <span className="text-[#9D4EDD]"> Ended</span> elections are archived for historical transparency.
              </p>
            </div>

            {/* Step 2 */}
            <div className="p-6 rounded-xl bg-[#0a0a18] border border-[#9D4EDD]/20 hover:border-[#00E5FF]/50 transition-colors">
              <h3 className="text-xl font-bold text-[#00E5FF] mb-3 flex items-center gap-2">
                <span className="flex items-center justify-center w-6 h-6 rounded-full bg-[#00E5FF]/10 text-[#00E5FF] text-xs">2</span>
                Viewing Results
              </h3>
              <p className="text-[#E0F7FA]/80 leading-relaxed pl-8">
                Click <strong>"View Election"</strong> on any active card to see real-time voting data. Since this interface is for public observation only, no wallet connection or voting privileges are required to view the data.
              </p>
            </div>

            {/* Step 3 */}
            <div className="p-6 rounded-xl bg-[#0a0a18] border border-[#9D4EDD]/20 hover:border-[#00E5FF]/50 transition-colors">
              <h3 className="text-xl font-bold text-[#00E5FF] mb-3 flex items-center gap-2">
                <span className="flex items-center justify-center w-6 h-6 rounded-full bg-[#00E5FF]/10 text-[#00E5FF] text-xs">3</span>
                Verification
              </h3>
              <p className="text-[#E0F7FA]/80 leading-relaxed pl-8">
                Every vote is cryptographically secured. You can verify the integrity of the results by cross-referencing the Election ID displayed on the card with the public ledger.
              </p>
            </div>
          </div>

        </div>
      </div>
    </Layout>
  );
};

export default HelpPage;