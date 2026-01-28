/* import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import Layout from '../components/Layout';

const BASE_URL = 'https://votechain.tail841e2c.ts.net:8443';

const ElectionListPage = () => {
  const [elections, setElections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");

useEffect(() => {
    document.title = `VoteChain`;
    const fetchElections = async () => {
      try {
        const response = await axios.get(`${BASE_URL}/elections`);
        setElections(response.data);
     } catch (err) {
        console.error("Error fetching elections:", err);
        setError("Failed to load elections.");
      } finally {
        setLoading(false);
      }
    };

    // Initial fetch
    fetchElections();

    // 2. The WebSocket Connection (The Real-Time Part)
    // We convert http://127.0.0.1... to ws://127.0.0.1...
    const wsBaseUrl = BASE_URL.replace('http', 'ws');
    const socket = new WebSocket(`${wsBaseUrl}/ws/elections/`);

    socket.onopen = () => {
      console.log("Connected to Election Lobby");
    };

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);

      // If the backend says "Update!", we fetch the new list immediately
      if (data.type === "ELECTION_UPDATE") {
        console.log("New election data detected. Refreshing list...");
        fetchElections();
      }
    };

    socket.onclose = () => {
      console.log("Disconnected from Lobby");
    };

    // Cleanup: Close connection when user leaves the page
    return () => {
      socket.close();
    };
  }, []); // Run once on mount

  const filteredElections = elections.filter(e =>
    e.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    e.election_id?.toString().includes(searchTerm)
  );

  const now = new Date();

  // An election is ACTIVE only if the switch is ON *and* time hasn't run out
  const activeElections = filteredElections.filter(e =>
    e.is_active && new Date(e.end_date) > now
  );

  // An election is PAST if the switch is OFF *or* time has run out
  const pastElections = filteredElections.filter(e =>
    !e.is_active || new Date(e.end_date) <= now
  );

  const getPlaceholderImage = (id, type) =>
    `https://picsum.photos/seed/${id + type}/600/400?grayscale&blur=2`;

  return (
    <Layout>
      <div className="px-6 lg:px-20 py-8">
        <div className="max-w-7xl mx-auto flex flex-col gap-10">

          <section className="flex flex-col md:flex-row justify-between items-center gap-4">
            <h1 className="text-[#E0F7FA] text-3xl font-bold">Elections</h1>
            <input
              className="w-full md:w-auto bg-[#0a0a18] border border-[#9D4EDD]/30 text-[#E0F7FA] h-12 px-4 rounded-xl outline-none focus:border-[#00E5FF]"
              placeholder="Search election..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </section>

          {loading && <div className="text-[#00E5FF] animate-pulse">Loading...</div>}
          {error && <div className="text-red-400">{error}</div>}

          {!loading && !error && (
            <section>
              <h2 className="text-[#00E5FF] text-xl font-bold mb-6">Ongoing Elections</h2>
              {activeElections.length === 0 ? (
                <p className="text-[#9D4EDD] italic">No active elections found.</p>
              ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {activeElections.map((election) => (
                    <div key={election.election_id} className="flex flex-col md:flex-row rounded-xl bg-[#0a0a18] border border-[#9D4EDD]/20 overflow-hidden hover:border-[#00E5FF] transition-all">
                      <div className="w-full md:w-48 h-48 md:h-auto bg-cover bg-center relative" style={{ backgroundImage: `url("${getPlaceholderImage(election.election_id, 'active')}")` }}>
                        <div className="absolute top-3 left-3 bg-[#050511]/80 text-[#00E5FF] text-xs font-bold px-2 py-1 rounded border border-[#00E5FF]/20">LIVE</div>
                      </div>
                      <div className="p-6 flex flex-col justify-between flex-1">
                        <h3 className="text-[#E0F7FA] text-xl font-bold">{election.name}</h3>
                        <Link to={`/election/${election.election_id}`} className="mt-4 text-center rounded-full h-10 px-6 bg-[#00E5FF] text-[#050511] font-bold flex items-center justify-center">View Election</Link>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          {!loading && !error && (
            <section className="opacity-80 hover:opacity-100 transition-opacity duration-500 pt-8">
              <div className="flex items-center gap-3 mb-6">
                <h2 className="text-[#9D4EDD] text-xl font-bold">Past Elections</h2>
                <div className="h-px flex-1 bg-gradient-to-r from-[#9D4EDD]/50 to-transparent"></div>
              </div>

              {pastElections.length === 0 ? (
                <p className="text-[#9D4EDD] italic">No past elections found.</p>
              ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {pastElections.map((election) => (
                    <Link
                      to={`/election/${election.election_id}`}
                      key={election.election_id}
                      className="relative flex flex-col md:flex-row rounded-xl bg-[#0a0a18] border border-[#9D4EDD]/10 overflow-hidden grayscale hover:grayscale-0 transition-all duration-300 group"
                    >
                      <div
                        className="w-full md:w-48 h-48 md:h-auto bg-cover bg-center shrink-0 relative"
                        style={{ backgroundImage: `url("${getPlaceholderImage(election.election_id, 'past')}")` }}
                      >
                        <div className="absolute inset-0 bg-[#050511]/60"></div>
                        <div className="absolute top-3 left-3 bg-[#050511]/80 backdrop-blur-md text-gray-400 text-xs font-bold px-2 py-1 rounded flex items-center gap-1 border border-gray-600">
                          ENDED
                        </div>
                      </div>

                      <div className="flex flex-col justify-between p-6 flex-1 gap-4">
                        <div>
                          <h3 className="text-gray-300 text-xl font-bold leading-tight mb-2 group-hover:text-[#E0F7FA]">{election.name}</h3>
                          <p className="text-gray-500 text-sm">ID: {election.election_id}</p>
                        </div>
                        <div className="flex items-center justify-between text-sm">
                          <div className="flex flex-col gap-1">
                            <span className="text-gray-500 text-xs uppercase">Ended On</span>
                            <span className="text-gray-300 font-medium">
                              {new Date(election.end_date).toLocaleDateString()}
                            </span>
                          </div>
                          <div className="flex flex-col gap-1 text-right">
                            <span className="text-gray-500 text-xs uppercase">Result</span>
                            <span className="text-[#FF9E00] font-bold bg-[#FF9E00]/10 px-2 py-0.5 rounded text-xs border border-[#FF9E00]/20">VIEW RESULTS</span>
                          </div>
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </section>
          )}

        </div>
      </div>
    </Layout>
  );
};

export default ElectionListPage;
*/

// MOCK PAGE WITHOUT API

import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Layout from '../components/Layout';

const MOCK_ELECTIONS = [
  {
    election_id: "mock-1",
    name: "2025 Student Council Election",
    is_active: true,
    end_date: new Date(new Date().getTime() + 86400000).toISOString(), // Ends tomorrow
  },
  {
    election_id: "mock-2",
    name: "Faculty Senate Referendum",
    is_active: false,
    end_date: "2023-11-01T12:00:00Z", // Past date
  }
];

const ElectionListPage = () => {
  const [elections, setElections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    document.title = `VoteChain`;

    const loadMockData = () => {
        setTimeout(() => {
            setElections(MOCK_ELECTIONS);
            setLoading(false);
        }, 500);
    };

    loadMockData();

  }, []); 

  const filteredElections = elections.filter(e =>
    e.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    e.election_id?.toString().includes(searchTerm)
  );

  const now = new Date();
  const activeElections = filteredElections.filter(e =>
    e.is_active && new Date(e.end_date) > now
  );
  
  const pastElections = filteredElections.filter(e =>
    !e.is_active || new Date(e.end_date) <= now
  );

  const getPlaceholderImage = (id, type) =>
    `https://picsum.photos/seed/${id + type}/600/400?grayscale&blur=2`;

  return (
    <Layout>
      <div className="px-6 lg:px-20 py-8">
        <div className="max-w-7xl mx-auto flex flex-col gap-10">

          {/* Search */}
          <section className="flex flex-col md:flex-row justify-between items-center gap-4">
            <h1 className="text-[#E0F7FA] text-3xl font-bold">Elections</h1>
            <input
              className="w-full md:w-auto bg-[#0a0a18] border border-[#9D4EDD]/30 text-[#E0F7FA] h-12 px-4 rounded-xl outline-none focus:border-[#00E5FF]"
              placeholder="Search election..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </section>

          {loading && <div className="text-[#00E5FF] animate-pulse">Loading...</div>}
          {error && <div className="text-red-400">{error}</div>}

          {/* Active List */}
          {!loading && !error && (
            <section>
              <h2 className="text-[#00E5FF] text-xl font-bold mb-6">Ongoing Elections</h2>
              {activeElections.length === 0 ? (
                <p className="text-[#9D4EDD] italic">No active elections found.</p>
              ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {activeElections.map((election) => (
                    <div key={election.election_id} className="flex flex-col md:flex-row rounded-xl bg-[#0a0a18] border border-[#9D4EDD]/20 overflow-hidden hover:border-[#00E5FF] transition-all">
                      <div className="w-full md:w-48 h-48 md:h-auto bg-cover bg-center relative" style={{ backgroundImage: `url("${getPlaceholderImage(election.election_id, 'active')}")` }}>
                        <div className="absolute top-3 left-3 bg-[#050511]/80 text-[#00E5FF] text-xs font-bold px-2 py-1 rounded border border-[#00E5FF]/20">LIVE</div>
                      </div>
                      <div className="p-6 flex flex-col justify-between flex-1">
                        <h3 className="text-[#E0F7FA] text-xl font-bold">{election.name}</h3>
                        <Link to={`/election/${election.election_id}`} className="mt-4 text-center rounded-full h-10 px-6 bg-[#00E5FF] text-[#050511] font-bold flex items-center justify-center">View Election</Link>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          {/* Past List */}
          {!loading && !error && (
            <section className="opacity-80 hover:opacity-100 transition-opacity duration-500 pt-8">
              <div className="flex items-center gap-3 mb-6">
                <h2 className="text-[#9D4EDD] text-xl font-bold">Past Elections</h2>
                <div className="h-px flex-1 bg-gradient-to-r from-[#9D4EDD]/50 to-transparent"></div>
              </div>

              {pastElections.length === 0 ? (
                <p className="text-[#9D4EDD] italic">No past elections found.</p>
              ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {pastElections.map((election) => (
                    <Link
                      to={`/election/${election.election_id}`}
                      key={election.election_id}
                      className="relative flex flex-col md:flex-row rounded-xl bg-[#0a0a18] border border-[#9D4EDD]/10 overflow-hidden grayscale hover:grayscale-0 transition-all duration-300 group"
                    >
                      <div
                        className="w-full md:w-48 h-48 md:h-auto bg-cover bg-center shrink-0 relative"
                        style={{ backgroundImage: `url("${getPlaceholderImage(election.election_id, 'past')}")` }}
                      >
                        <div className="absolute inset-0 bg-[#050511]/60"></div>
                        <div className="absolute top-3 left-3 bg-[#050511]/80 backdrop-blur-md text-gray-400 text-xs font-bold px-2 py-1 rounded flex items-center gap-1 border border-gray-600">
                          ENDED
                        </div>
                      </div>

                      <div className="flex flex-col justify-between p-6 flex-1 gap-4">
                        <div>
                          <h3 className="text-gray-300 text-xl font-bold leading-tight mb-2 group-hover:text-[#E0F7FA]">{election.name}</h3>
                          <p className="text-gray-500 text-sm">ID: {election.election_id}</p>
                        </div>
                        <div className="flex items-center justify-between text-sm">
                          <div className="flex flex-col gap-1">
                            <span className="text-gray-500 text-xs uppercase">Ended On</span>
                            <span className="text-gray-300 font-medium">
                              {new Date(election.end_date).toLocaleDateString()}
                            </span>
                          </div>
                          <div className="flex flex-col gap-1 text-right">
                            <span className="text-gray-500 text-xs uppercase">Result</span>
                            <span className="text-[#FF9E00] font-bold bg-[#FF9E00]/10 px-2 py-0.5 rounded text-xs border border-[#FF9E00]/20">VIEW RESULTS</span>
                          </div>
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </section>
          )}

        </div>
      </div>
    </Layout>
  );
};

export default ElectionListPage;
