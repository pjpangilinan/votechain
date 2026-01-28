/*
import React, { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import Layout from '../components/Layout';

const BASE_URL = 'https://votechain.tail841e2c.ts.net:8443';

const ElectionDashboard = () => {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [activeTab, setActiveTab] = useState(0);
  const [timeLeft, setTimeLeft] = useState("");
  const [loading, setLoading] = useState(true);

  const [expandedBlock, setExpandedBlock] = useState(null);

  const fetchDashboardData = useCallback(async () => {
    try {
      const response = await axios.get(`${BASE_URL}/dashboard/${id}/`);
      setData(response.data);
      setLoading(false);
    } catch (err) {
      console.error("Error fetching dashboard:", err);
    }
  }, [id]);

  useEffect(() => {
    fetchDashboardData();

    const wsBaseUrl = BASE_URL.replace('http', 'ws');
    const socket = new WebSocket(`${wsBaseUrl}/ws/dashboard/${id}/`);

    socket.onopen = () => {
      console.log(`Connected to Dashboard Stream: ${id}`);
    };

    socket.onmessage = (event) => {
      console.log("New vote detected! Refreshing...", event.data);
      fetchDashboardData();
    };

    return () => {
      socket.close();
    };
  }, [id, fetchDashboardData]);

  // 3. Countdown Timer Logic
  useEffect(() => {
    if (!data) return;
    const timer = setInterval(() => {
      const end = new Date(data.metadata.end_date).getTime();
      const now = new Date().getTime();
      const distance = end - now;

      if (distance < 0) {
        setTimeLeft("ELECTION ENDED");
      } else {
        const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((distance % (1000 * 60)) / 1000);
        setTimeLeft(`${hours}h ${minutes}m ${seconds}s`);
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [data]);

  const toggleBlock = (hash) => {
    if (expandedBlock === hash) {
      setExpandedBlock(null);
    } else {
      setExpandedBlock(hash);
    }
  };

  if (loading) return <Layout><div className="text-[#00E5FF] p-10 text-center animate-pulse">Initializing Blockchain Connection...</div></Layout>;
  if (!data) return <Layout><div className="text-[#FF9E00] p-10 text-center">Error: Unable to load election contract.</div></Layout>;

  const currentPosition = data.positions[activeTab];

  return (
    <Layout>
      <div className="px-6 lg:px-20 py-8 max-w-[1600px] mx-auto">

        <div className="flex flex-col lg:flex-row justify-between items-end gap-6 mb-8">

            <div className="flex flex-col gap-2 max-w-3xl">
                <div className="flex flex-wrap items-center gap-4 mb-1">
                    <span className={`px-3 py-1 rounded border ${data.metadata.is_active ? 'bg-[#00E5FF]/10 border-[#00E5FF] text-[#00E5FF]' : 'bg-[#9D4EDD]/10 border-[#9D4EDD] text-[#9D4EDD]'} text-xs font-bold uppercase tracking-wider`}>
                        {data.metadata.is_active ? "● Live Network" : "○ Consensus Finalized"}
                    </span>

                    <span className="text-[#9D4EDD] text-sm font-mono flex items-center gap-1">
                        Contract: {id.slice(0, 8)}...{id.slice(-4)}
                    </span>

                    <span className="text-[#FF9E00] text-sm font-mono font-bold flex items-center gap-2 border-l border-[#9D4EDD]/30 pl-4">
                        ⏳ {timeLeft}
                    </span>
                </div>

                <h1 className="text-4xl lg:text-6xl font-bold tracking-tight text-[#E0F7FA] drop-shadow-[0_0_10px_rgba(0,229,255,0.3)]">
                    {data.metadata.name}
                </h1>
                <p className="text-[#9D4EDD] text-lg">{data.metadata.description}</p>
            </div>

            <div className="flex gap-8 lg:border-l lg:border-[#9D4EDD]/20 lg:pl-8 pb-1">
                 <div className="flex flex-col items-end">
                    <span className="text-[#9D4EDD] text-[10px] font-bold uppercase tracking-widest mb-1">Total Votes</span>
                    <span className="text-4xl font-mono font-bold text-[#E0F7FA]">{data.stats.total_votes}</span>
                 </div>

                 <div className="flex flex-col items-end">
                    <span className="text-[#9D4EDD] text-[10px] font-bold uppercase tracking-widest mb-1">Turnout</span>
                    <span className="text-4xl font-mono font-bold text-[#00E5FF]">{data.stats.turnout}%</span>
                 </div>
            </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">

            <div className="lg:col-span-7 flex flex-col gap-8">

                <div className="flex border-b border-[#9D4EDD]/30 gap-8 overflow-x-auto pb-1 scrollbar-hide">
                    {data.positions.map((pos, index) => (
                        <button
                            key={pos.id}
                            onClick={() => setActiveTab(index)}
                            className={`relative pb-4 px-2 font-bold text-sm tracking-wide transition-all uppercase whitespace-nowrap ${
                                index === activeTab
                                ? "text-[#00E5FF] drop-shadow-[0_0_8px_rgba(0,229,255,0.8)]"
                                : "text-[#9D4EDD] hover:text-[#E0F7FA]"
                            }`}
                        >
                            {pos.title}
                            {index === activeTab && (
                                <span className="absolute bottom-0 left-0 w-full h-0.5 bg-[#00E5FF] shadow-[0_0_10px_#00E5FF]"></span>
                            )}
                        </button>
                    ))}
                </div>

                <div className="flex flex-col gap-5">
                    {currentPosition ? (
                        currentPosition.candidates.map((candidate) => (
                            <div key={candidate.id} className="relative group p-5 rounded-xl bg-[#0a0a18] border border-[#9D4EDD]/20 hover:border-[#00E5FF] transition-all overflow-hidden">
                                <div
                                    className="absolute left-0 top-0 bottom-0 bg-[#00E5FF]/5 z-0 transition-all duration-1000 group-hover:bg-[#00E5FF]/10"
                                    style={{ width: `${candidate.percentage}%` }}
                                ></div>

                                <div className="relative z-10 flex items-center gap-5">
                                    <div className="size-16 rounded-lg border-2 border-[#9D4EDD]/50 p-0.5 shrink-0 bg-[#050511]">
                                        <img
                                            alt={candidate.name}
                                            className="w-full h-full object-cover rounded"
                                            src={candidate.photo ? `${BASE_URL}${candidate.photo}` : `https://ui-avatars.com/api/?name=${candidate.name}&background=050511&color=00E5FF`}
                                        />
                                    </div>

                                    <div className="flex-1 min-w-0">
                                        <div className="flex justify-between items-baseline mb-1">
                                            <h3 className="text-lg font-bold truncate text-[#E0F7FA] group-hover:text-[#00E5FF] transition-colors">
                                                {candidate.name}
                                            </h3>
                                            <span className="text-2xl font-mono font-bold text-[#00E5FF] drop-shadow-[0_0_5px_rgba(0,229,255,0.5)]">
                                                {candidate.percentage}%
                                            </span>
                                        </div>
                                        <div className="flex justify-between text-xs text-[#9D4EDD] font-mono uppercase tracking-wide mb-3">
                                            <span>{candidate.party || "Independent"}</span>
                                            <span>{candidate.votes} Votes</span>
                                        </div>
                                        <div className="w-full bg-[#050511] border border-[#9D4EDD]/20 rounded-full h-2 overflow-hidden">
                                            <div
                                                className="bg-gradient-to-r from-[#9D4EDD] to-[#00E5FF] h-full shadow-[0_0_15px_rgba(0,229,255,0.8)]"
                                                style={{ width: `${candidate.percentage}%` }}
                                            ></div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ))
                    ) : (
                        <p className="text-[#9D4EDD] italic">No positions configured.</p>
                    )}
                </div>
            </div>

            <div className="lg:col-span-5 flex flex-col h-full">
                <div className="flex items-center justify-between mb-6 pb-2 border-b border-[#00E5FF]/20">
                    <h2 className="text-xl font-bold text-[#E0F7FA] flex items-center gap-2">
                        <span className="text-[#00E5FF] animate-pulse">●</span> Public Ledger
                    </h2>
                </div>

                <div className="bg-[#050511] rounded-xl border border-[#00E5FF]/30 overflow-hidden flex flex-col shadow-[inset_0_0_20px_rgba(0,0,0,0.8)] h-[800px]">
                    <div className="grid grid-cols-12 gap-2 p-3 bg-[#0a0a18] border-b border-[#00E5FF]/20 text-[10px] font-mono text-[#9D4EDD] uppercase tracking-wider">
                        <div className="col-span-2">Block</div>
                        <div className="col-span-7">Transaction Hash</div>
                        <div className="col-span-3 text-right">Time</div>
                    </div>

                    <div className="overflow-y-auto flex-1 font-mono text-xs custom-scrollbar">
                        {data.ledger.map((block, idx) => (
                            <div key={idx} className="border-b border-[#00E5FF]/10">
                                <div
                                    onClick={() => toggleBlock(block.current_hash)}
                                    className={`grid grid-cols-12 gap-2 p-3 cursor-pointer transition-colors ${
                                        expandedBlock === block.current_hash
                                            ? "bg-[#00E5FF]/10 text-[#00E5FF]"
                                            : "hover:bg-[#00E5FF]/5 text-[#E0F7FA]/60"
                                    }`}
                                >
                                    <div className="col-span-2 font-bold text-[#FF9E00]">
                                        {data.stats.blocks_mined - idx}
                                    </div>
                                    <div className="col-span-7 truncate" title={block.current_hash}>
                                        {block.current_hash}
                                    </div>
                                    <div className="col-span-3 text-right">
                                        {expandedBlock === block.current_hash ? "▼" : block.timestamp}
                                    </div>
                                </div>

                                {expandedBlock === block.current_hash && (
                                    <div className="bg-[#0a0a18] p-4 border-t border-[#00E5FF]/20 shadow-inner animate-[fadeIn_0.2s_ease-out]">
                                        <div className="flex flex-col gap-3">
                                            <div>
                                                <p className="text-[10px] text-[#9D4EDD] uppercase tracking-widest mb-1">Decrypted Ballot Data</p>
                                                <div className="bg-[#050511] p-3 rounded border border-[#9D4EDD]/20">
                                                    {Object.entries(block.ballot_data).map(([position, candidateName], i) => (
                                                        <div key={i} className="flex justify-between items-center py-1 border-b border-[#9D4EDD]/10 last:border-0">
                                                            <span className="text-[#E0F7FA] font-bold">{position}</span>
                                                            <span className="text-[#00E5FF]">{Array.isArray(candidateName) ? candidateName.join(", ") : candidateName}</span>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                            <div className="grid grid-cols-1 gap-2">
                                                <div>
                                                    <p className="text-[10px] text-[#9D4EDD] uppercase tracking-widest">Full Hash</p>
                                                    <p className="text-[10px] text-[#E0F7FA]/50 break-all">{block.current_hash}</p>
                                                </div>
                                                <div>
                                                    <p className="text-[10px] text-[#9D4EDD] uppercase tracking-widest">Timestamp</p>
                                                    <p className="text-[#E0F7FA]">{block.timestamp}</p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
      </div>
    </Layout>
  );
};

export default ElectionDashboard;
*/

// MOCK PAGE WITHOUT API
import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import Layout from '../components/Layout';

const MOCK_DATA = {
  metadata: {
    name: "2025 Student Council Election",
    description: "Official voting for the Student Body President and Treasurer positions. Ensure you have reviewed the candidates' manifestos.",
    is_active: true,
    end_date: new Date(new Date().getTime() + 172800000).toISOString(), 
  },
  stats: {
    total_votes: 1243,
    turnout: 76.5,
    blocks_mined: 89,
  },
  positions: [
    {
      id: 1,
      title: "President",
      candidates: [
        { id: 101, name: "Sarah Connor", percentage: 55, votes: 683, party: "Tech Forward", photo: null },
        { id: 102, name: "John Smith", percentage: 45, votes: 560, party: "Tradition Union", photo: null },
      ]
    },
    {
      id: 2,
      title: "Treasurer",
      candidates: [
        { id: 201, name: "Alice Wong", percentage: 30, votes: 372, party: "Independent", photo: null },
        { id: 202, name: "Bob Miller", percentage: 70, votes: 871, party: "Tech Forward", photo: null },
      ]
    }
  ],
  ledger: [
    { current_hash: "0x8f2a...9d12", timestamp: "14:32", ballot_data: { "President": "Sarah Connor", "Treasurer": "Bob Miller" } },
    { current_hash: "0x7b1c...4e33", timestamp: "14:30", ballot_data: { "President": "John Smith", "Treasurer": "Alice Wong" } },
    { current_hash: "0x6d9e...2a11", timestamp: "14:28", ballot_data: { "President": "Sarah Connor", "Treasurer": "Bob Miller" } },
    { current_hash: "0x5c4f...1b99", timestamp: "14:25", ballot_data: { "President": "Sarah Connor", "Treasurer": "Bob Miller" } },
  ]
};

const ElectionDashboard = () => {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [activeTab, setActiveTab] = useState(0);
  const [timeLeft, setTimeLeft] = useState("");
  const [loading, setLoading] = useState(true);
  const [expandedBlock, setExpandedBlock] = useState(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setData(MOCK_DATA);
      setLoading(false);
    }, 800);

    return () => clearTimeout(timer);
  }, []); 

  useEffect(() => {
    if (!data) return;
    const timer = setInterval(() => {
      const end = new Date(data.metadata.end_date).getTime();
      const now = new Date().getTime();
      const distance = end - now;

      if (distance < 0) {
        setTimeLeft("ELECTION ENDED");
      } else {
        const days = Math.floor(distance / (1000 * 60 * 60 * 24));
        const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((distance % (1000 * 60)) / 1000);
        
        if (days > 0) {
           setTimeLeft(`${days}d ${hours}h ${minutes}m ${seconds}s`);
        } else {
           setTimeLeft(`${hours}h ${minutes}m ${seconds}s`);
        }
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [data]);

  const toggleBlock = (hash) => {
    if (expandedBlock === hash) {
      setExpandedBlock(null);
    } else {
      setExpandedBlock(hash);
    }
  };

  const formatLedgerTime = (timestamp) => {
    if (!timestamp) return "--";
    const str = timestamp.toString();
    const match = str.match(/(\d{1,2}):\d{2}/);
    if (match) {
        const hour = match[1].padStart(2, '0');
        return `${hour}:00`; /
    }
    return str;
  };

  if (loading) return <Layout><div className="text-[#00E5FF] p-10 text-center animate-pulse">Initializing Blockchain Connection...</div></Layout>;
  if (!data) return <Layout><div className="text-[#FF9E00] p-10 text-center">Error: Unable to load election contract.</div></Layout>;

  const currentPosition = data.positions[activeTab];

  return (
    <Layout>
      <div className="px-6 lg:px-20 py-8 max-w-[1600px] mx-auto">

        <div className="flex flex-col lg:flex-row justify-between items-end gap-6 mb-8">
            <div className="flex flex-col gap-2 max-w-3xl">
                <div className="flex flex-wrap items-center gap-4 mb-1">
                    <span className={`px-3 py-1 rounded border ${data.metadata.is_active ? 'bg-[#00E5FF]/10 border-[#00E5FF] text-[#00E5FF]' : 'bg-[#9D4EDD]/10 border-[#9D4EDD] text-[#9D4EDD]'} text-xs font-bold uppercase tracking-wider`}>
                        {data.metadata.is_active ? "● Live Network" : "● Consensus Finalized"}
                    </span>
                    <span className="text-[#9D4EDD] text-sm font-mono flex items-center gap-1">
                        Contract: {id ? `${id.slice(0, 8)}...${id.slice(-4)}` : "0xMOCK...DATA"}
                    </span>
                    <span className="text-[#FF9E00] text-sm font-mono font-bold flex items-center gap-2 border-l border-[#9D4EDD]/30 pl-4">
                        ⏳ {timeLeft}
                    </span>
                </div>

                <h1 className="text-4xl lg:text-6xl font-bold tracking-tight text-[#E0F7FA] drop-shadow-[0_0_10px_rgba(0,229,255,0.3)]">
                    {data.metadata.name}
                </h1>
                <p className="text-[#9D4EDD] text-lg">{data.metadata.description}</p>
            </div>

            <div className="flex gap-8 lg:border-l lg:border-[#9D4EDD]/20 lg:pl-8 pb-1">
                 <div className="flex flex-col items-end">
                    <span className="text-[#9D4EDD] text-[10px] font-bold uppercase tracking-widest mb-1">Total Votes</span>
                    <span className="text-4xl font-mono font-bold text-[#E0F7FA]">{data.stats.total_votes}</span>
                 </div>
                 <div className="flex flex-col items-end">
                    <span className="text-[#9D4EDD] text-[10px] font-bold uppercase tracking-widest mb-1">Turnout</span>
                    <span className="text-4xl font-mono font-bold text-[#00E5FF]">{data.stats.turnout}%</span>
                 </div>
            </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">

            <div className="lg:col-span-7 flex flex-col gap-8">
                <div className="flex border-b border-[#9D4EDD]/30 gap-8 overflow-x-auto pb-1 scrollbar-hide">
                    {data.positions.map((pos, index) => (
                        <button
                            key={pos.id}
                            onClick={() => setActiveTab(index)}
                            className={`relative pb-4 px-2 font-bold text-sm tracking-wide transition-all uppercase whitespace-nowrap ${
                                index === activeTab
                                ? "text-[#00E5FF] drop-shadow-[0_0_8px_rgba(0,229,255,0.8)]"
                                : "text-[#9D4EDD] hover:text-[#E0F7FA]"
                            }`}
                        >
                            {pos.title}
                            {index === activeTab && (
                                <span className="absolute bottom-0 left-0 w-full h-0.5 bg-[#00E5FF] shadow-[0_0_10px_#00E5FF]"></span>
                            )}
                        </button>
                    ))}
                </div>

                <div className="flex flex-col gap-5">
                    {currentPosition ? (
                        currentPosition.candidates.map((candidate) => (
                            <div key={candidate.id} className="relative group p-5 rounded-xl bg-[#0a0a18] border border-[#9D4EDD]/20 hover:border-[#00E5FF] transition-all overflow-hidden">
                                <div
                                    className="absolute left-0 top-0 bottom-0 bg-[#00E5FF]/5 z-0 transition-all duration-1000 group-hover:bg-[#00E5FF]/10"
                                    style={{ width: `${candidate.percentage}%` }}
                                ></div>

                                <div className="relative z-10 flex items-center gap-5">
                                    <div className="size-16 rounded-lg border-2 border-[#9D4EDD]/50 p-0.5 shrink-0 bg-[#050511]">
                                        <img
                                            alt={candidate.name}
                                            className="w-full h-full object-cover rounded"
                                            src={candidate.photo ? candidate.photo : `https://ui-avatars.com/api/?name=${candidate.name}&background=050511&color=00E5FF`}
                                        />
                                    </div>

                                    <div className="flex-1 min-w-0">
                                        <div className="flex justify-between items-baseline mb-1">
                                            <h3 className="text-lg font-bold truncate text-[#E0F7FA] group-hover:text-[#00E5FF] transition-colors">
                                                {candidate.name}
                                            </h3>
                                            <span className="text-2xl font-mono font-bold text-[#00E5FF] drop-shadow-[0_0_5px_rgba(0,229,255,0.5)]">
                                                {candidate.percentage}%
                                            </span>
                                        </div>
                                        <div className="flex justify-between text-xs text-[#9D4EDD] font-mono uppercase tracking-wide mb-3">
                                            <span>{candidate.party || "Independent"}</span>
                                            <span>{candidate.votes} Votes</span>
                                        </div>
                                        <div className="w-full bg-[#050511] border border-[#9D4EDD]/20 rounded-full h-2 overflow-hidden">
                                            <div
                                                className="bg-gradient-to-r from-[#9D4EDD] to-[#00E5FF] h-full shadow-[0_0_15px_rgba(0,229,255,0.8)]"
                                                style={{ width: `${candidate.percentage}%` }}
                                            ></div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ))
                    ) : (
                        <p className="text-[#9D4EDD] italic">No positions configured.</p>
                    )}
                </div>
            </div>

            <div className="lg:col-span-5 flex flex-col h-full">
                <div className="flex items-center justify-between mb-6 pb-2 border-b border-[#00E5FF]/20">
                    <h2 className="text-xl font-bold text-[#E0F7FA] flex items-center gap-2">
                        <span className="text-[#00E5FF] animate-pulse">●</span> Public Ledger
                    </h2>
                </div>

                <div className="bg-[#050511] rounded-xl border border-[#00E5FF]/30 overflow-hidden flex flex-col shadow-[inset_0_0_20px_rgba(0,0,0,0.8)] h-[800px]">
                    <div className="grid grid-cols-12 gap-2 p-3 bg-[#0a0a18] border-b border-[#00E5FF]/20 text-[10px] font-mono text-[#9D4EDD] uppercase tracking-wider">
                        <div className="col-span-2">Block</div>
                        <div className="col-span-7">Transaction Hash</div>
                        <div className="col-span-3 text-right">Time</div>
                    </div>

                    <div className="overflow-y-auto flex-1 font-mono text-xs custom-scrollbar">
                        {data.ledger.map((block, idx) => (
                            <div key={idx} className="border-b border-[#00E5FF]/10">
                                <div
                                    onClick={() => toggleBlock(block.current_hash)}
                                    className={`grid grid-cols-12 gap-2 p-3 cursor-pointer transition-colors ${
                                        expandedBlock === block.current_hash
                                            ? "bg-[#00E5FF]/10 text-[#00E5FF]"
                                            : "hover:bg-[#00E5FF]/5 text-[#E0F7FA]/60"
                                    }`}
                                >
                                    <div className="col-span-2 font-bold text-[#FF9E00]">
                                        {data.stats.blocks_mined - idx}
                                    </div>
                                    <div className="col-span-7 truncate" title={block.current_hash}>
                                        {block.current_hash}
                                    </div>
                                    <div className="col-span-3 text-right">
                                        {expandedBlock === block.current_hash ? "▼" : formatLedgerTime(block.timestamp)}
                                    </div>
                                </div>

                                {expandedBlock === block.current_hash && (
                                    <div className="bg-[#0a0a18] p-4 border-t border-[#00E5FF]/20 shadow-inner animate-[fadeIn_0.2s_ease-out]">
                                        <div className="flex flex-col gap-3">
                                            <div>
                                                <p className="text-[10px] text-[#9D4EDD] uppercase tracking-widest mb-1">Decrypted Ballot Data</p>
                                                <div className="bg-[#050511] p-3 rounded border border-[#9D4EDD]/20">
                                                    {Object.entries(block.ballot_data).map(([position, candidateName], i) => (
                                                        <div key={i} className="flex justify-between items-center py-1 border-b border-[#9D4EDD]/10 last:border-0">
                                                            <span className="text-[#E0F7FA] font-bold">{position}</span>
                                                            <span className="text-[#00E5FF]">{Array.isArray(candidateName) ? candidateName.join(", ") : candidateName}</span>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                            <div className="grid grid-cols-1 gap-2">
                                                <div>
                                                   <p className="text-[10px] text-[#9D4EDD] uppercase tracking-widest">Full Hash</p>
                                                   <p className="text-[10px] text-[#E0F7FA]/50 break-all">{block.current_hash}</p>
                                                </div>
                                                <div>
                                                    <p className="text-[10px] text-[#9D4EDD] uppercase tracking-widest">Timestamp</p>
                                                    <p className="text-[#E0F7FA]">{formatLedgerTime(block.timestamp)}</p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
      </div>
    </Layout>
  );
};

export default ElectionDashboard;
