const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8001";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    },
    ...options
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Request failed");
  }

  return response.json();
}

export function saveProfile(profile) {
  return request("/profiles", {
    method: "POST",
    body: JSON.stringify(profile)
  });
}

export function fetchProfile(employeeId) {
  return request(`/profiles/${employeeId}`);
}

export function fetchRecommendations(employeeId) {
  return request("/recommendations", {
    method: "POST",
    body: JSON.stringify({ employee_id: employeeId, top_k: 5 })
  });
}

export function fetchEmployeeIntelligence(employeeId) {
  return request(`/employee-intelligence/${employeeId}`);
}

export function sendChatMessage(payload) {
  return request("/chat", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function fetchDocuments() {
  return request("/documents");
}

export function fetchExternalCourses(query, topK = 10) {
  const params = new URLSearchParams({ query, top_k: String(topK) });
  return request(`/courses/search?${params.toString()}`);
}

export function fetchProgress(employeeId) {
  return request(`/progress/${employeeId}`);
}

export function updateCourseProgress(payload) {
  return request("/progress", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function fetchModuleProgress(employeeId) {
  return request(`/module-progress/${employeeId}`);
}

export function updateModuleProgress(payload) {
  return request("/module-progress", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function fetchRoadmap(employeeId) {
  return request(`/roadmap/${employeeId}`);
}

export function fetchAdminSummary() {
  return request("/admin/summary");
}
