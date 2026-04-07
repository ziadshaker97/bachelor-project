import { useEffect, useState } from "react";
import { fetchDocuments, fetchRecommendations, saveProfile, sendChatMessage } from "./api";

const initialProfile = {
  employee_id: "emp-demo-001",
  role: "Software Engineer",
  department: "Platform",
  experience_level: "beginner",
  known_skills: ["security awareness"],
  learning_preferences: ["video", "interactive"]
};

const initialSession = `session-${Date.now()}`;

function App() {
  const [profile, setProfile] = useState(initialProfile);
  const [recommendations, setRecommendations] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [messages, setMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [sessionId] = useState(initialSession);
  const [status, setStatus] = useState("Fill in the profile, save it, then fetch recommendations.");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchDocuments()
      .then((payload) => setDocuments(payload.documents))
      .catch(() => setDocuments([]));
  }, []);

  const skillString = profile.known_skills.join(", ");
  const prefString = profile.learning_preferences.join(", ");

  async function handleSaveProfile(event) {
    event.preventDefault();
    setLoading(true);
    setStatus("Saving employee profile...");
    try {
      const normalized = {
        ...profile,
        known_skills: profile.known_skills,
        learning_preferences: profile.learning_preferences
      };
      await saveProfile(normalized);
      setStatus("Profile saved. You can fetch recommendations or start chatting.");
    } catch (error) {
      setStatus(`Could not save profile: ${error.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleRecommendations() {
    setLoading(true);
    setStatus("Generating recommendations...");
    try {
      const payload = await fetchRecommendations(profile.employee_id);
      setRecommendations(payload.recommendations);
      setStatus("Recommendations updated.");
    } catch (error) {
      setStatus(`Could not load recommendations: ${error.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleChatSubmit(event) {
    event.preventDefault();
    if (!chatInput.trim()) {
      return;
    }

    const outgoing = chatInput.trim();
    setMessages((current) => [...current, { speaker: "user", text: outgoing }]);
    setChatInput("");
    setLoading(true);
    setStatus("Asking the onboarding assistant...");

    try {
      const response = await sendChatMessage({
        session_id: sessionId,
        employee_id: profile.employee_id,
        message: outgoing
      });

      setMessages((current) => [
        ...current,
        {
          speaker: "assistant",
          text: response.answer,
          sources: response.sources,
          recommended_module_ids: response.recommended_module_ids || []
        }
      ]);
      setStatus("Assistant response grounded in indexed documents.");
    } catch (error) {
      setMessages((current) => [
        ...current,
        { speaker: "assistant", text: `Error: ${error.message}` }
      ]);
      setStatus("Chat request failed.");
    } finally {
      setLoading(false);
    }
  }

  function updateField(field, value) {
    setProfile((current) => ({ ...current, [field]: value }));
  }

  return (
    <div className="shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Employee Onboarding Intelligence</p>
          <h1>Personalized onboarding recommendations and grounded document chat.</h1>
        </div>
        <p className="status">{status}</p>
      </header>

      <main className="grid">
        <section className="panel">
          <h2>Employee Profile</h2>
          <form onSubmit={handleSaveProfile} className="form">
            <label>
              Employee ID
              <input
                value={profile.employee_id}
                onChange={(event) => updateField("employee_id", event.target.value)}
              />
            </label>
            <label>
              Role
              <input value={profile.role} onChange={(event) => updateField("role", event.target.value)} />
            </label>
            <label>
              Department
              <input
                value={profile.department}
                onChange={(event) => updateField("department", event.target.value)}
              />
            </label>
            <label>
              Experience Level
              <select
                value={profile.experience_level}
                onChange={(event) => updateField("experience_level", event.target.value)}
              >
                <option value="beginner">Beginner</option>
                <option value="intermediate">Intermediate</option>
                <option value="advanced">Advanced</option>
              </select>
            </label>
            <label>
              Known Skills
              <input
                value={skillString}
                onChange={(event) =>
                  updateField(
                    "known_skills",
                    event.target.value.split(",").map((item) => item.trim()).filter(Boolean)
                  )
                }
              />
            </label>
            <label>
              Learning Preferences
              <input
                value={prefString}
                onChange={(event) =>
                  updateField(
                    "learning_preferences",
                    event.target.value.split(",").map((item) => item.trim()).filter(Boolean)
                  )
                }
              />
            </label>
            <div className="buttonRow">
              <button type="submit" disabled={loading}>Save Profile</button>
              <button type="button" disabled={loading} onClick={handleRecommendations}>
                Get Recommendations
              </button>
            </div>
          </form>
        </section>

        <section className="panel">
          <h2>Recommended Modules</h2>
          <div className="cardList">
            {recommendations.length === 0 ? (
              <p className="empty">No recommendations yet. Save the profile and request them.</p>
            ) : (
              recommendations.map((item) => (
                <article key={item.module_id} className="recommendationCard">
                  <div className="score">{item.score}</div>
                  <div>
                    <h3>{item.module_id}</h3>
                    <p>{item.reason_text}</p>
                    <p className="meta">{item.reason_codes.join(" · ")}</p>
                  </div>
                </article>
              ))
            )}
          </div>
        </section>

        <section className="panel chatPanel">
          <h2>Onboarding Assistant</h2>
          <div className="chatStream">
            {messages.length === 0 ? (
              <p className="empty">Ask about leave, access, policies, or onboarding steps.</p>
            ) : (
              messages.map((message, index) => (
                <article key={`${message.speaker}-${index}`} className={`chatBubble ${message.speaker}`}>
                  <p>{message.text}</p>
                  {message.sources?.length ? (
                    <div className="sources">
                      {message.sources.map((source) => (
                        <div key={`${source.document_id}-${source.title}`} className="sourceItem">
                          <strong>{source.title}</strong>
                          <span>{source.snippet}</span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                  {message.recommended_module_ids?.length ? (
                    <p className="meta">
                      Related modules: {message.recommended_module_ids.join(", ")}
                    </p>
                  ) : null}
                </article>
              ))
            )}
          </div>
          <form onSubmit={handleChatSubmit} className="chatComposer">
            <textarea
              value={chatInput}
              onChange={(event) => setChatInput(event.target.value)}
              rows={4}
              placeholder="Ask the assistant a question about onboarding..."
            />
            <button type="submit" disabled={loading}>Send</button>
          </form>
        </section>

        <section className="panel">
          <h2>Indexed Documents</h2>
          <div className="cardList">
            {documents.map((doc) => (
              <article key={doc.document_id} className="documentCard">
                <h3>{doc.title}</h3>
                <p className="meta">{doc.category}</p>
                <p>{doc.content.slice(0, 180)}...</p>
              </article>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
