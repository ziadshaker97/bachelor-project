import { useEffect, useMemo, useState } from "react";
import {
  fetchAdminSummary,
  fetchDocuments,
  fetchEmployeeIntelligence,
  fetchExternalCourses,
  fetchModuleProgress,
  fetchProfile,
  fetchProgress,
  fetchRecommendations,
  fetchRoadmap,
  sendChatMessage,
  updateModuleProgress,
  updateCourseProgress
} from "./api";
import backgroundArt from "./background-art.svg";

const initialSession = `session-${Date.now()}`;
const starterEmployeeId = "emp-demo-001";
const sharedOnboardingModuleIds = new Set(["mod-security-101", "mod-hr-policy", "mod-customer-context"]);

function formatCourseMeta(course) {
  const parts = [course.provider, course.category];
  if (typeof course.duration_hours === "number" && course.duration_hours > 0) {
    parts.push(`${course.duration_hours} hours`);
  }
  return parts.join(" - ");
}

function formatProgressStage(stage) {
  return stage
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function formatActionType(actionType) {
  const labels = {
    module: "Internal module",
    course: "Course",
    practice: "On-the-job practice"
  };
  return labels[actionType] || actionType;
}

function simplifyReason(reasonText) {
  if (!reasonText) {
    return "Recommended for your current role and progress.";
  }
  if (reasonText.startsWith("Predicted next-best module from the local recommender model")) {
    const gap = reasonText.split("likely skill gap:")[1]?.replace(".", "").trim();
    return gap ? `Recommended to strengthen ${gap}.` : "Recommended from your current learning profile.";
  }
  return reasonText.split(";")[0];
}

function formatList(items, fallback) {
  return items.length ? items.join(", ") : fallback;
}

function roadmapStatusLabel(status) {
  if (status === "completed") {
    return "Completed";
  }
  if (status === "active") {
    return "In progress";
  }
  return "Upcoming";
}

function App() {
  const [employeeIdInput, setEmployeeIdInput] = useState(starterEmployeeId);
  const [profile, setProfile] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [modules, setModules] = useState([]);
  const [courses, setCourses] = useState([]);
  const [messages, setMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [sessionId] = useState(initialSession);
  const [status, setStatus] = useState("Enter your ID to continue.");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState([]);
  const [roadmap, setRoadmap] = useState([]);
  const [moduleProgress, setModuleProgress] = useState([]);
  const [adminSummary, setAdminSummary] = useState(null);
  const [intelligence, setIntelligence] = useState(null);
  const [courseSearch, setCourseSearch] = useState("");
  const [courseFilter, setCourseFilter] = useState("all");
  const [onlineCourses, setOnlineCourses] = useState([]);
  const [onlineCoursesConfigured, setOnlineCoursesConfigured] = useState(false);
  const [onlineProvider, setOnlineProvider] = useState("external");
  const [onlineLoading, setOnlineLoading] = useState(false);
  const [employeeView, setEmployeeView] = useState("home");
  const [adminView, setAdminView] = useState("overview");
  const [activeCourse, setActiveCourse] = useState(null);
  const [activeModule, setActiveModule] = useState(null);

  useEffect(() => {
    fetchDocuments()
      .then((payload) => {
        setCourses(payload.courses || []);
        setModules(payload.modules || []);
      })
      .catch(() => {
        setCourses([]);
        setModules([]);
      });
  }, []);

  async function loadEmployeeWorkspace(employeeId, nextProfile) {
    const [progressPayload, moduleProgressPayload, roadmapPayload, recommendationsPayload, intelligencePayload] = await Promise.all([
      fetchProgress(employeeId),
      fetchModuleProgress(employeeId),
      fetchRoadmap(employeeId),
      fetchRecommendations(employeeId),
      fetchEmployeeIntelligence(employeeId)
    ]);
    setProgress(progressPayload.progress || []);
    setModuleProgress(moduleProgressPayload.progress || []);
    setRoadmap(roadmapPayload.milestones || []);
    setRecommendations(recommendationsPayload.recommendations || []);
    setIntelligence(intelligencePayload);
    setStatus(`Welcome ${nextProfile.employee_id}.`);
  }

  async function refreshEmployeePlan(employeeId) {
    const [moduleProgressPayload, roadmapPayload, recommendationsPayload, intelligencePayload] = await Promise.all([
      fetchModuleProgress(employeeId),
      fetchRoadmap(employeeId),
      fetchRecommendations(employeeId),
      fetchEmployeeIntelligence(employeeId)
    ]);
    setModuleProgress(moduleProgressPayload.progress || []);
    setRoadmap(roadmapPayload.milestones || []);
    setRecommendations(recommendationsPayload.recommendations || []);
    setIntelligence(intelligencePayload);
  }

  async function loadAdminWorkspace(nextProfile) {
    const payload = await fetchAdminSummary();
    setAdminSummary(payload);
    setStatus(`Welcome ${nextProfile.employee_id}. Admin dashboard ready.`);
  }

  async function refreshAdminSummary() {
    try {
      const payload = await fetchAdminSummary();
      setAdminSummary(payload);
    } catch {
      setAdminSummary(null);
    }
  }

  async function handleLogin(event) {
    event.preventDefault();
    if (!employeeIdInput.trim()) {
      setStatus("Enter a valid ID.");
      return;
    }

    setLoading(true);
    setStatus("Checking your ID...");
    try {
      const payload = await fetchProfile(employeeIdInput.trim());
      const nextProfile = payload.profile;
      setProfile(nextProfile);
      setRecommendations([]);
      setMessages([]);
      setProgress([]);
      setModuleProgress([]);
      setRoadmap([]);
      setAdminSummary(null);
      setIntelligence(null);
      setChatInput("");
      setCourseSearch("");
      setCourseFilter("all");
      setOnlineCourses([]);
      setActiveCourse(null);
      setActiveModule(null);

      if (nextProfile.access_level === "admin") {
        setAdminView("overview");
        await loadAdminWorkspace(nextProfile);
      } else {
        setEmployeeView("home");
        await loadEmployeeWorkspace(nextProfile.employee_id, nextProfile);
      }
    } catch (error) {
      setProfile(null);
      setStatus(`Could not find ID: ${error.message}`);
    } finally {
      setLoading(false);
    }
  }

  function handleLogout() {
    setProfile(null);
    setRecommendations([]);
    setMessages([]);
    setProgress([]);
    setModuleProgress([]);
    setRoadmap([]);
    setAdminSummary(null);
    setIntelligence(null);
    setChatInput("");
    setCourseSearch("");
    setCourseFilter("all");
    setOnlineCourses([]);
    setActiveCourse(null);
    setActiveModule(null);
    setStatus("Signed out. Enter your ID to continue.");
  }

  async function handleRecommendations() {
    if (!profile || profile.access_level === "admin") {
      return;
    }

    setLoading(true);
    setStatus("Refreshing your learning plan...");
    try {
      const payload = await fetchRecommendations(profile.employee_id);
      setRecommendations(payload.recommendations);
      const intelligencePayload = await fetchEmployeeIntelligence(profile.employee_id);
      setIntelligence(intelligencePayload);
      setStatus("Learning plan refreshed.");
    } catch (error) {
      setStatus(`Could not load recommendations: ${error.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleChatSubmit(event) {
    event.preventDefault();
    if (!chatInput.trim() || !profile || profile.access_level === "admin") {
      return;
    }

    const outgoing = chatInput.trim();
    setMessages((current) => [...current, { speaker: "user", text: outgoing }]);
    setChatInput("");
    setLoading(true);
    setStatus("Assistant is thinking...");

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
          recommended_module_ids: response.recommended_module_ids || [],
          recommended_courses: response.recommended_courses || []
        }
      ]);
      setStatus("Assistant response ready.");
    } catch (error) {
      setMessages((current) => [...current, { speaker: "assistant", text: `Error: ${error.message}` }]);
      setStatus("Chat request failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleExternalCourseSearch() {
    if (!courseSearch.trim()) {
      setOnlineCourses([]);
      setStatus("Enter a topic to search online courses.");
      return;
    }

    setOnlineLoading(true);
    setStatus("Searching external course catalog...");
    try {
      const payload = await fetchExternalCourses(courseSearch.trim(), 12);
      setOnlineCourses(payload.courses || []);
      setOnlineCoursesConfigured(Boolean(payload.configured));
      setOnlineProvider(payload.provider || "external");
      if (!payload.courses?.length) {
        setStatus("No external courses were found for that topic.");
      } else {
        setStatus("Online course results loaded.");
      }
    } catch (error) {
      setStatus(`Could not search external courses: ${error.message}`);
      setOnlineCourses([]);
    } finally {
      setOnlineLoading(false);
    }
  }

  function openCourse(course) {
    if (!course?.url) {
      setActiveCourse(course);
      return;
    }
    window.open(course.url, "_blank", "noopener,noreferrer");
  }

  function openModule(module) {
    setActiveModule(module);
  }

  async function handleCourseAction(course, action) {
    if (!profile || profile.access_level === "admin") {
      return;
    }

    const existing = progress.find((item) => item.course_id === course.course_id);
    const payloadByAction = {
      start: {
        employee_id: profile.employee_id,
        course_id: course.course_id,
        status: "in_progress",
        progress_percent: existing?.progress_percent ? Math.max(existing.progress_percent, 25) : 25,
        saved_for_later: false
      },
      complete: {
        employee_id: profile.employee_id,
        course_id: course.course_id,
        status: "completed",
        progress_percent: 100,
        saved_for_later: false
      },
      save: {
        employee_id: profile.employee_id,
        course_id: course.course_id,
        status: existing?.status || "not_started",
        progress_percent: existing?.progress_percent || 0,
        saved_for_later: true
      }
    };

    setLoading(true);
    setStatus("Updating course progress...");
    try {
      const progressPayload = await updateCourseProgress(payloadByAction[action]);
      setProgress(progressPayload.progress || []);
      await refreshEmployeePlan(profile.employee_id);
      await refreshAdminSummary();
      setStatus("Course progress updated.");
      if (action === "start") {
        openCourse(course);
      }
    } catch (error) {
      setStatus(`Could not update course progress: ${error.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleModuleAction(module, action) {
    if (!profile || profile.access_level === "admin") {
      return;
    }

    const existing = moduleProgress.find((item) => item.module_id === module.module_id);
    const payloadByAction = {
      start: {
        employee_id: profile.employee_id,
        module_id: module.module_id,
        status: "in_progress",
        progress_percent: existing?.progress_percent ? Math.max(existing.progress_percent, 25) : 25,
        saved_for_later: false
      },
      complete: {
        employee_id: profile.employee_id,
        module_id: module.module_id,
        status: "completed",
        progress_percent: 100,
        saved_for_later: false
      },
      save: {
        employee_id: profile.employee_id,
        module_id: module.module_id,
        status: existing?.status || "not_started",
        progress_percent: existing?.progress_percent || 0,
        saved_for_later: true
      }
    };

    setLoading(true);
    setStatus("Updating module progress...");
    try {
      const payload = await updateModuleProgress(payloadByAction[action]);
      setModuleProgress(payload.progress || []);
      await refreshEmployeePlan(profile.employee_id);
      setStatus("Module progress updated.");
      if (action === "start") {
        openModule(module);
      }
    } catch (error) {
      setStatus(`Could not update module progress: ${error.message}`);
    } finally {
      setLoading(false);
    }
  }

  const progressByCourseId = useMemo(
    () => Object.fromEntries(progress.map((item) => [item.course_id, item])),
    [progress]
  );
  const moduleProgressById = useMemo(
    () => Object.fromEntries(moduleProgress.map((item) => [item.module_id, item])),
    [moduleProgress]
  );
  const modulesById = useMemo(
    () => Object.fromEntries(modules.map((item) => [item.module_id, item])),
    [modules]
  );

  const filteredCourses = useMemo(() => {
    return courses.filter((course) => {
      const progressItem = progressByCourseId[course.course_id];
      const searchable = `${course.title} ${course.description} ${course.category} ${course.provider} ${course.skills.join(" ")}`.toLowerCase();
      const matchesSearch = searchable.includes(courseSearch.toLowerCase());
      if (!matchesSearch) {
        return false;
      }
      if (courseFilter === "all") {
        return true;
      }
      if (courseFilter === "completed") {
        return progressItem?.status === "completed";
      }
      if (courseFilter === "in_progress") {
        return progressItem?.status === "in_progress";
      }
      if (courseFilter === "saved") {
        return Boolean(progressItem?.saved_for_later);
      }
      return true;
    });
  }, [courseFilter, courseSearch, courses, progressByCourseId]);

  const progressStats = useMemo(() => {
    const completed = progress.filter((item) => item.status === "completed").length;
    const inProgress = progress.filter((item) => item.status === "in_progress").length;
    const saved = progress.filter((item) => item.saved_for_later).length;
    const completionRate = progress.length ? Math.round((completed / progress.length) * 100) : 0;
    return { completed, inProgress, saved, completionRate };
  }, [progress]);

  const nextCourseActions = useMemo(() => {
    if (!profile) {
      return [];
    }
    const courseMap = Object.fromEntries(courses.map((course) => [course.course_id, course]));
    const progressPriority = [
      ...progress
        .filter((item) => item.status === "in_progress")
        .sort((left, right) => right.progress_percent - left.progress_percent)
        .map((item) => item.course_id),
      ...progress
        .filter((item) => item.saved_for_later && item.status !== "completed")
        .map((item) => item.course_id)
    ];
    const profileMatches = courses
      .filter((course) => {
        const searchable = `${course.title} ${course.description} ${course.tags.join(" ")} ${course.skills.join(" ")}`.toLowerCase();
        return (
          searchable.includes(profile.role.toLowerCase()) ||
          searchable.includes(profile.department.toLowerCase()) ||
          profile.known_skills.some((skill) => searchable.includes(skill.toLowerCase()))
        );
      })
      .map((course) => course.course_id);

    return [...new Set([...progressPriority, ...profileMatches])]
      .map((courseId) => courseMap[courseId])
      .filter(Boolean)
      .slice(0, 3);
  }, [courses, profile, progress]);

  const filteredModules = useMemo(() => {
    if (!profile) {
      return [];
    }
    const role = profile.role.toLowerCase();
    const department = profile.department.toLowerCase();
    return modules.filter((module) => {
      if (sharedOnboardingModuleIds.has(module.module_id)) {
        return false;
      }
      const roleTags = (module.role_tags || []).map((tag) => tag.toLowerCase());
      const topics = (module.topic_tags || []).map((tag) => tag.toLowerCase());
      return (
        roleTags.includes(role) ||
        topics.includes(department)
      );
    });
  }, [modules, profile]);

  const primaryRecommendation = useMemo(() => {
    if (!recommendations.length) {
      return null;
    }
    const lead = recommendations[0];
    return {
      ...lead,
      title: modulesById[lead.module_id]?.title || lead.module_id
    };
  }, [modulesById, recommendations]);

  function renderProgressBadge(courseId) {
    const item = progressByCourseId[courseId];
    if (!item) {
      return <span className="progressBadge neutral">Not started</span>;
    }
    if (item.status === "completed") {
      return <span className="progressBadge success">Completed</span>;
    }
    if (item.status === "in_progress") {
      return <span className="progressBadge info">{item.progress_percent}% in progress</span>;
    }
    if (item.saved_for_later) {
      return <span className="progressBadge warning">Saved</span>;
    }
    return <span className="progressBadge neutral">Not started</span>;
  }

  function renderCourseActions(course) {
    const openLabel = course.delivery_mode === "internal" ? "View Course" : "Open Course";
    return (
      <div className="actionRow">
        <button type="button" disabled={loading} onClick={() => handleCourseAction(course, "start")}>Start</button>
        <button type="button" className="secondaryButton" disabled={loading} onClick={() => openCourse(course)}>{openLabel}</button>
        <button type="button" className="ghostButton" disabled={loading} onClick={() => handleCourseAction(course, "complete")}>Complete</button>
        <button type="button" className="ghostButton" disabled={loading} onClick={() => handleCourseAction(course, "save")}>Save</button>
      </div>
    );
  }

  function renderModuleProgressBadge(moduleId) {
    const item = moduleProgressById[moduleId];
    if (!item) {
      return <span className="progressBadge neutral">Not started</span>;
    }
    if (item.status === "completed") {
      return <span className="progressBadge success">Completed</span>;
    }
    if (item.status === "in_progress") {
      return <span className="progressBadge info">{item.progress_percent}% in progress</span>;
    }
    if (item.saved_for_later) {
      return <span className="progressBadge warning">Saved</span>;
    }
    return <span className="progressBadge neutral">Not started</span>;
  }

  function renderModuleActions(module) {
    return (
      <div className="actionRow">
        <button type="button" disabled={loading} onClick={() => handleModuleAction(module, "start")}>Start Module</button>
        <button type="button" className="secondaryButton" disabled={loading} onClick={() => openModule(module)}>View Module</button>
        <button type="button" className="ghostButton" disabled={loading} onClick={() => handleModuleAction(module, "complete")}>Complete</button>
        <button type="button" className="ghostButton" disabled={loading} onClick={() => handleModuleAction(module, "save")}>Save</button>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="shell authShell" style={{ "--page-art": `url(${backgroundArt})` }}>
        <section className="authCard">
          <p className="eyebrow">Employee Onboarding Intelligence</p>
          <h1>Sign in</h1>
          <p className="authSubhead">Access your onboarding workspace</p>
          <form onSubmit={handleLogin} className="form">
            <label>
              ID
              <input value={employeeIdInput} onChange={(event) => setEmployeeIdInput(event.target.value)} />
            </label>
            <div className="buttonRow">
              <button type="submit" disabled={loading}>Continue</button>
            </div>
          </form>
          <p className="statusText subtleStatus">{status}</p>
        </section>
      </div>
    );
  }

  if (profile.access_level === "admin") {
    return (
      <div className="shell" style={{ "--page-art": `url(${backgroundArt})` }}>
        <div className="cmsLayout">
          <aside className="cmsSidebar">
            <div className="brandBlock sidebarBrand">
              <span className="brandMark">EOI</span>
              <div>
                <strong>Employee Onboarding Intelligence</strong>
                <p>Admin Console</p>
              </div>
            </div>
            <div className="sidebarSection">
              <p className="sectionEyebrow">Navigation</p>
              <button type="button" className={`sidebarLink ${adminView === "overview" ? "active" : ""}`} onClick={() => setAdminView("overview")}>Overview</button>
              <button type="button" className={`sidebarLink ${adminView === "employees" ? "active" : ""}`} onClick={() => setAdminView("employees")}>Employees</button>
            </div>
            <div className="sidebarSection sidebarFooter">
              <p className="sectionEyebrow">Session</p>
              <p className="meta">{profile.employee_id}</p>
              <button type="button" className="ghostButton fullWidth" onClick={handleLogout}>Logout</button>
            </div>
          </aside>

          <main className="cmsContent">
            <header className="hero compactHero">
              <div className="heroText">
                <p className="eyebrow">Admin Dashboard</p>
                <h1>{adminView === "overview" ? "Team onboarding overview" : "Employee onboarding status"}</h1>
                <p className="heroLead">Monitor onboarding health, adoption, and employee progress from one controlled workspace.</p>
              </div>
            </header>

            {adminView === "overview" ? (
              <section className="panel">
                <div className="sectionHeader">
                  <div>
                    <p className="sectionEyebrow">Summary</p>
                    <h2>Platform Metrics</h2>
                  </div>
                </div>
                {adminSummary ? (
                  <div className="adminMetrics">
                    <article className="metricCard"><span>Employees</span><strong>{adminSummary.total_employees}</strong></article>
                    <article className="metricCard"><span>Started</span><strong>{adminSummary.total_courses_started}</strong></article>
                    <article className="metricCard"><span>Completed</span><strong>{adminSummary.total_courses_completed}</strong></article>
                    <article className="metricCard"><span>Average completion</span><strong>{adminSummary.average_completion_rate}%</strong></article>
                  </div>
                ) : (
                  <p className="empty">Admin summary is unavailable.</p>
                )}
              </section>
            ) : null}

            {adminView === "employees" ? (
              <section className="panel">
                <div className="sectionHeader">
                  <div>
                    <p className="sectionEyebrow">Employees</p>
                    <h2>Onboarding Status</h2>
                  </div>
                </div>
                <div className="employeeTable">
                  {adminSummary?.employee_summaries.map((item) => (
                    <article key={item.employee_id} className="tableRow">
                      <div>
                        <strong>{item.employee_id}</strong>
                        <p className="meta">{item.role} - {item.department}</p>
                      </div>
                      <div className="tableMetrics">
                        <span>{item.completed_courses} completed</span>
                        <span>{item.in_progress_courses} active</span>
                        <span>{item.saved_courses} saved</span>
                        <span>{item.completion_rate}% completion</span>
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            ) : null}
          </main>
        </div>
      </div>
    );
  }

  return (
    <div className="shell" style={{ "--page-art": `url(${backgroundArt})` }}>
      <div className="cmsLayout">
        <aside className="cmsSidebar">
          <div className="brandBlock sidebarBrand">
            <span className="brandMark">EOI</span>
            <div>
              <strong>Employee Onboarding Intelligence</strong>
              <p>Employee Workspace</p>
            </div>
          </div>
          <div className="sidebarSection">
            <p className="sectionEyebrow">Menu</p>
            <button type="button" className={`sidebarLink ${employeeView === "home" ? "active" : ""}`} onClick={() => setEmployeeView("home")}>Home</button>
            <button type="button" className={`sidebarLink ${employeeView === "roadmap" ? "active" : ""}`} onClick={() => setEmployeeView("roadmap")}>Roadmap</button>
            <button type="button" className={`sidebarLink ${employeeView === "modules" ? "active" : ""}`} onClick={() => setEmployeeView("modules")}>Modules</button>
            <button type="button" className={`sidebarLink ${employeeView === "assistant" ? "active" : ""}`} onClick={() => setEmployeeView("assistant")}>Assistant</button>
            <button type="button" className={`sidebarLink ${employeeView === "courses" ? "active" : ""}`} onClick={() => setEmployeeView("courses")}>Courses</button>
          </div>
          <div className="sidebarSection sidebarFooter">
            <p className="sectionEyebrow">Account</p>
            <p className="meta">{profile.employee_id}</p>
            <p className="meta">{profile.role} - {profile.department}</p>
            <button type="button" className="ghostButton fullWidth" onClick={handleLogout}>Logout</button>
          </div>
        </aside>

        <main className="cmsContent">
          {employeeView === "home" ? (
            <>
              <header className="hero compactHero">
                <div className="heroText">
                  <p className="eyebrow">Employee Home</p>
                  <h1>Welcome, {profile.employee_id}</h1>
                  <p className="heroLead">Your onboarding workspace keeps the most important employee context in one place.</p>
                </div>
                <div className="statusPanel">
                  <span className="statusLabel">Current status</span>
                  <p>{status}</p>
                  <div className="buttonRow topSpace">
                    <button type="button" onClick={handleRecommendations} disabled={loading}>Refresh Plan</button>
                  </div>
                </div>
              </header>

              <div className="contentGrid">
                <section className="panel">
                  <div className="sectionHeader">
                    <div>
                      <p className="sectionEyebrow">Profile</p>
                      <h2>Employee Summary</h2>
                    </div>
                  </div>
                  <div className="profileSummary">
                    <div className="profileGrid">
                      <p><strong>Role</strong><span>{profile.role}</span></p>
                      <p><strong>Department</strong><span>{profile.department}</span></p>
                      <p><strong>Experience</strong><span>{profile.experience_level}</span></p>
                      <p><strong>ID</strong><span>{profile.employee_id}</span></p>
                    </div>
                    <p><strong>Skills</strong><span className="inlineValue">{profile.known_skills.join(", ") || "None saved"}</span></p>
                    <p><strong>Preferences</strong><span className="inlineValue">{profile.learning_preferences.join(", ") || "None saved"}</span></p>
                  </div>
                </section>

                <section className="panel">
                  <div className="sectionHeader">
                    <div>
                      <p className="sectionEyebrow">Progress</p>
                      <h2>Learning Overview</h2>
                    </div>
                  </div>
                  <div className="metricStack">
                    <article className="metricCard"><span>Completion</span><strong>{progressStats.completionRate}%</strong></article>
                    <article className="metricCard"><span>Completed</span><strong>{progressStats.completed}</strong></article>
                    <article className="metricCard"><span>In progress</span><strong>{progressStats.inProgress}</strong></article>
                    <article className="metricCard"><span>Saved</span><strong>{progressStats.saved}</strong></article>
                  </div>
                </section>
              </div>

              <section className="panel">
                <div className="sectionHeader">
                  <div>
                    <p className="sectionEyebrow">AI Engine</p>
                    <h2>Learning Snapshot</h2>
                  </div>
                </div>
                {intelligence ? (
                  <div className="insightStack">
                    <article className="documentCard">
                      <div className="actionCardHeader">
                        <h3>{formatProgressStage(intelligence.progress_stage)}</h3>
                        <span className="progressBadge info">AI overview</span>
                      </div>
                      <p>{intelligence.ai_message}</p>
                    </article>
                    <div className="insightGrid">
                      <article className="documentCard">
                        <h3>Strongest Areas</h3>
                        <p className="meta">{formatList(intelligence.strengths, "Building core onboarding strengths")}</p>
                      </article>
                      <article className="documentCard">
                        <h3>Growth Areas</h3>
                        <p className="meta">{formatList(intelligence.skill_gaps, "Ready for deeper ownership")}</p>
                      </article>
                      <article className="documentCard">
                        <h3>Current Focus</h3>
                        <p className="meta">{primaryRecommendation ? primaryRecommendation.title : "Your next recommendation will appear here."}</p>
                      </article>
                    </div>
                  </div>
                ) : (
                  <p className="empty">AI engine is preparing your recommendation pulse.</p>
                )}
              </section>

              <section className="panel">
                <div className="sectionHeader">
                  <div>
                    <p className="sectionEyebrow">Action Center</p>
                    <h2>What To Do Next</h2>
                  </div>
                </div>
                {intelligence?.next_steps?.length || nextCourseActions.length ? (
                  <div className="actionCenterGrid">
                    {intelligence?.next_steps?.map((step, index) => (
                      <article key={`${step.action_type}-${index}`} className="documentCard">
                        <div className="actionCardHeader">
                          <h3>{step.title}</h3>
                          <span className="progressBadge neutral">{formatActionType(step.action_type)}</span>
                        </div>
                        <p>{step.detail}</p>
                      </article>
                    ))}
                    {nextCourseActions.map((course) => (
                      <article key={course.course_id} className="documentCard">
                        <div className="actionCardHeader">
                          <div>
                            <h3>{course.title}</h3>
                            <p className="meta">{formatCourseMeta(course)}</p>
                          </div>
                          {renderProgressBadge(course.course_id)}
                        </div>
                        <p>{course.description}</p>
                        {renderCourseActions(course)}
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="empty">Start a course or open the library to build your onboarding plan.</p>
                )}
              </section>

              <section className="panel">
                <div className="sectionHeader">
                  <div>
                    <p className="sectionEyebrow">AI Recommendations</p>
                    <h2>Recommended Modules</h2>
                  </div>
                </div>
                {recommendations.length ? (
                  <div className="employeeTable">
                    {recommendations.map((item, index) => (
                      <article key={item.module_id} className="tableRow">
                        <div className="actionCardHeader">
                          <div>
                            <p className="meta">Priority {index + 1}</p>
                            <h3>{modulesById[item.module_id]?.title || item.module_id}</h3>
                            <p className="meta">{simplifyReason(item.reason_text)}</p>
                          </div>
                          {renderModuleProgressBadge(item.module_id)}
                        </div>
                        <div className="recommendationFooter">
                          <span className="scoreChip">Match score {item.score}</span>
                        </div>
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="empty">AI recommendations will appear here after your profile loads.</p>
                )}
              </section>
            </>
          ) : null}

          {employeeView === "modules" ? (
            <section className="panel">
              <div className="sectionHeader">
                <div>
                  <p className="sectionEyebrow">Internal Learning</p>
                  <h2>Training Modules for Your Role</h2>
                </div>
              </div>
              <div className="libraryGrid">
                {filteredModules.map((module) => (
                  <article key={module.module_id} className="documentCard">
                    <div className="courseHeader">
                      <div>
                        <h3>{module.title}</h3>
                        <p className="meta">{module.format} - {module.difficulty}</p>
                      </div>
                      {renderModuleProgressBadge(module.module_id)}
                    </div>
                    <p>{module.description}</p>
                    <p className="meta">Topics: {module.topic_tags.join(", ")}</p>
                    {renderModuleActions(module)}
                  </article>
                ))}
              </div>
              {!filteredModules.length ? (
                <p className="empty">No internal modules are assigned to this role yet.</p>
              ) : null}
            </section>
          ) : null}

          {employeeView === "roadmap" ? (
            <section className="panel">
              <div className="sectionHeader">
                <div>
                  <p className="sectionEyebrow">Roadmap</p>
                  <h2>Your Professional Growth Timeline</h2>
                </div>
              </div>
              <div className="timeline roadmapTimeline">
                {roadmap.map((item) => (
                  <article key={item.milestone_id} className={`timelineItem roadmapCard ${item.status || "upcoming"}`}>
                    <div className="courseHeader">
                      <div>
                        <span className="timelinePhase">{item.phase}</span>
                        <h3>{item.title}</h3>
                      </div>
                      <span className={`progressBadge ${item.status === "completed" ? "success" : item.status === "active" ? "info" : "neutral"}`}>
                        {roadmapStatusLabel(item.status)}
                      </span>
                    </div>
                    <div className="roadmapMeter">
                      <div className="roadmapMeterFill" style={{ width: `${item.progress_percent || 0}%` }} />
                    </div>
                    <p className="meta">{item.progress_percent || 0}% complete</p>
                    <p>{item.description}</p>
                    {item.evidence?.length ? (
                      <div className="sources compactSources">
                        {item.evidence.map((entry, index) => (
                          <div key={`${item.milestone_id}-${index}`} className="sourceItem">
                            <strong>Training evidence</strong>
                            <span>{entry}</span>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          {employeeView === "assistant" ? (
            <section className="panel chatPanel">
              <div className="sectionHeader">
                <div>
                  <p className="sectionEyebrow">Assistant</p>
                  <h2>Ask anything about onboarding and company support</h2>
                </div>
              </div>
              <div className="chatShell">
              <div className="chatStream">
                {messages.length === 0 ? (
                  <div className="chatEmptyState">
                    <h3>Start a conversation</h3>
                    <p className="empty">Try questions like "How do I request leave?", "Who approves tool access?", or "What should I finish in my first week?"</p>
                  </div>
                ) : (
                  messages.map((message, index) => (
                    <article key={`${message.speaker}-${index}`} className={`chatMessage ${message.speaker}`}>
                      <div className="chatAvatar">{message.speaker === "user" ? "You" : "AI"}</div>
                      <div className={`chatBubble ${message.speaker}`}>
                      <p>{message.text}</p>
                      {message.sources?.length ? (
                        <div className="sources compactSources">
                          {message.sources.map((source) => (
                            <div key={`${source.document_id}-${source.title}`} className="sourceItem">
                              <strong>{source.title}</strong>
                              <span>{source.snippet}</span>
                            </div>
                          ))}
                        </div>
                      ) : null}
                      {message.recommended_courses?.length ? (
                        <div className="courseList">
                          {message.recommended_courses.map((course) => (
                            <article key={course.course_id} className="courseCard">
                              <div className="courseHeader">
                                <div>
                                  <h3>{course.title}</h3>
                                  <p className="meta">{formatCourseMeta(course)}</p>
                                </div>
                                {renderProgressBadge(course.course_id)}
                              </div>
                              <p>{course.description}</p>
                              {renderCourseActions(course)}
                            </article>
                          ))}
                        </div>
                      ) : null}
                      </div>
                    </article>
                  ))
                )}
              </div>
              <form onSubmit={handleChatSubmit} className="chatComposer">
                <textarea
                  value={chatInput}
                  onChange={(event) => setChatInput(event.target.value)}
                  placeholder="Message the assistant..."
                  disabled={loading}
                />
                <button type="submit" disabled={loading}>Send</button>
              </form>
              </div>
            </section>
          ) : null}

          {employeeView === "courses" ? (
            <section className="panel">
              <div className="sectionHeader">
                <div>
                  <p className="sectionEyebrow">Learning</p>
                  <h2>Course Library</h2>
                </div>
              </div>
              <div className="toolbar">
                <input
                  value={courseSearch}
                  onChange={(event) => setCourseSearch(event.target.value)}
                  placeholder="Search courses, skills, or providers..."
                />
                <select value={courseFilter} onChange={(event) => setCourseFilter(event.target.value)}>
                  <option value="all">All courses</option>
                  <option value="in_progress">In progress</option>
                  <option value="completed">Completed</option>
                  <option value="saved">Saved</option>
                </select>
                <button type="button" onClick={handleExternalCourseSearch} disabled={onlineLoading}>
                  {onlineLoading ? "Searching..." : "Search Online"}
                </button>
              </div>
              <section className="panel">
                <div className="sectionHeader">
                  <div>
                    <p className="sectionEyebrow">Online Discovery</p>
                    <h3>External Course Catalog</h3>
                  </div>
                </div>
                {onlineCourses.length ? (
                  <div className="libraryGrid">
                    {onlineCourses.map((course) => (
                      <article key={course.course_id} className="documentCard">
                        <div className="courseHeader">
                          <div>
                            <h3>{course.title}</h3>
                            <p className="meta">{formatCourseMeta(course)}</p>
                          </div>
                          <span className="progressBadge neutral">{onlineProvider.replaceAll("_", " ")}</span>
                        </div>
                        <p>{course.description}</p>
                        <p className="meta">Skills: {course.skills.join(", ") || "Not provided by provider"}</p>
                        {renderCourseActions(course)}
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="empty">Search a topic above to load Coursera, Udemy, and edX marketplace results.</p>
                )}
              </section>
              <div className="sectionHeader">
                <div>
                  <p className="sectionEyebrow">Internal Library</p>
                  <h3>Seeded Course Catalog</h3>
                </div>
              </div>
              <div className="libraryGrid">
                {filteredCourses.map((course) => (
                  <article key={course.course_id} className="documentCard">
                    <div className="courseHeader">
                      <div>
                        <h3>{course.title}</h3>
                        <p className="meta">{formatCourseMeta(course)}</p>
                      </div>
                      {renderProgressBadge(course.course_id)}
                    </div>
                    <p>{course.description}</p>
                    <p className="meta">Skills: {course.skills.join(", ")}</p>
                    {renderCourseActions(course)}
                  </article>
                ))}
              </div>
            </section>
          ) : null}
        </main>
      </div>
      {activeCourse ? (
        <div className="courseModalBackdrop" role="presentation" onClick={() => setActiveCourse(null)}>
          <section className="courseModal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="courseModalHeader">
              <div>
                <p className="sectionEyebrow">Course View</p>
                <h2>{activeCourse.title}</h2>
                <p className="meta">{formatCourseMeta(activeCourse)}</p>
              </div>
              <button type="button" className="ghostButton" onClick={() => setActiveCourse(null)}>Close</button>
            </div>
            <p>{activeCourse.description}</p>
            <div className="courseModalGrid">
              <article className="documentCard">
                <h3>Skills</h3>
                <p className="meta">{activeCourse.skills.join(", ") || "Topic-focused learning path"}</p>
              </article>
              <article className="documentCard">
                <h3>Delivery</h3>
                <p className="meta">
                  {activeCourse.delivery_mode === "internal"
                    ? "In-app guided learning path"
                    : "External provider course"}
                </p>
              </article>
            </div>
            <div className="sectionHeader">
              <div>
                <p className="sectionEyebrow">Outline</p>
                <h3>Learning Modules</h3>
              </div>
            </div>
            <div className="timeline">
              {(activeCourse.syllabus?.length ? activeCourse.syllabus : ["Open the provider course to view the full content outline."]).map((item, index) => (
                <article key={`${activeCourse.course_id}-${index}`} className="timelineItem">
                  <span className="timelinePhase">Module {index + 1}</span>
                  <h3>{item}</h3>
                </article>
              ))}
            </div>
            <div className="actionRow topSpace">
              <button type="button" disabled={loading} onClick={() => handleCourseAction(activeCourse, "start")}>Start Course</button>
              {activeCourse.url ? (
                <button type="button" className="secondaryButton" onClick={() => openCourse(activeCourse)}>Open Provider</button>
              ) : null}
              <button type="button" className="ghostButton" disabled={loading} onClick={() => handleCourseAction(activeCourse, "save")}>Save for Later</button>
            </div>
          </section>
        </div>
      ) : null}
      {activeModule ? (
        <div className="courseModalBackdrop" role="presentation" onClick={() => setActiveModule(null)}>
          <section className="courseModal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="courseModalHeader">
              <div>
                <p className="sectionEyebrow">Module View</p>
                <h2>{activeModule.title}</h2>
                <p className="meta">{activeModule.format} - {activeModule.difficulty}</p>
              </div>
              <button type="button" className="ghostButton" onClick={() => setActiveModule(null)}>Close</button>
            </div>
            <p>{activeModule.description}</p>
            <div className="courseModalGrid">
              <article className="documentCard">
                <h3>Topics</h3>
                <p className="meta">{activeModule.topic_tags.join(", ")}</p>
              </article>
              <article className="documentCard">
                <h3>Prerequisites</h3>
                <p className="meta">{activeModule.prerequisites.join(", ") || "No prerequisites"}</p>
              </article>
            </div>
            <div className="sectionHeader">
              <div>
                <p className="sectionEyebrow">Outline</p>
                <h3>Module Sections</h3>
              </div>
            </div>
            <div className="timeline">
              {(activeModule.syllabus?.length ? activeModule.syllabus : ["Review the module content and complete the guided internal tasks."]).map((item, index) => (
                <article key={`${activeModule.module_id}-${index}`} className="timelineItem">
                  <span className="timelinePhase">Section {index + 1}</span>
                  <h3>{item}</h3>
                </article>
              ))}
            </div>
            <div className="actionRow topSpace">
              <button type="button" disabled={loading} onClick={() => handleModuleAction(activeModule, "start")}>Start Module</button>
              <button type="button" className="ghostButton" disabled={loading} onClick={() => handleModuleAction(activeModule, "complete")}>Mark Complete</button>
              <button type="button" className="ghostButton" disabled={loading} onClick={() => handleModuleAction(activeModule, "save")}>Save for Later</button>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}

export default App;
