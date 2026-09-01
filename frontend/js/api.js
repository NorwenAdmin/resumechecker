const API = {
  async _req(method, path, body, opts_extra) {
    const allow401 = opts_extra && opts_extra.allow401;
    const opts = { method, headers: {} };
    if (body instanceof FormData) {
      opts.body = body;
    } else if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(path, opts);
    if (res.status === 401 && !allow401) {
      window.location.replace("/login.html");
      return new Promise(() => {}); // navigation is happening; don't resolve
    }
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const data = await res.json();
        detail = data.detail || detail;
      } catch (_) {}
      throw new Error(detail);
    }
    if (res.status === 204) return null;
    return res.json();
  },

  register: (email, password, name) => API._req("POST", "/api/auth/register", { email, password, name }),
  login: (email, password) => API._req("POST", "/api/auth/login", { email, password }),
  logout: () => API._req("POST", "/api/auth/logout"),
  me: () => API._req("GET", "/api/auth/me", undefined, { allow401: true }),

  onboardingStatus: () => API._req("GET", "/api/onboarding/status"),
  onboardingQuestions: () => API._req("GET", "/api/onboarding/questions"),
  uploadResumeFile: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return API._req("POST", "/api/onboarding/resume", fd);
  },
  uploadResumeText: (text) => {
    const fd = new FormData();
    fd.append("text", text);
    return API._req("POST", "/api/onboarding/resume", fd);
  },
  submitAnswers: (answers) => API._req("POST", "/api/onboarding/answers", { answers }),
  getAnswers: () => API._req("GET", "/api/onboarding/answers"),

  createJob: (raw_text, title, company) => API._req("POST", "/api/jobs", { raw_text, title, company }),
  listJobs: () => API._req("GET", "/api/jobs"),
  getJob: (id) => API._req("GET", `/api/jobs/${id}`),
  updateJobStatus: (id, status) => API._req("PATCH", `/api/jobs/${id}/status`, { status }),
  setConfirmedSkill: (id, skill, has_it) => API._req("PATCH", `/api/jobs/${id}/confirmed-skills`, { skill, has_it }),

  generateResume: (jobId) => API._req("POST", `/api/jobs/${jobId}/resume`),
  generateCoverLetter: (jobId) => API._req("POST", `/api/jobs/${jobId}/cover-letter`),
  editResume: (jobId, resumeId, content) => API._req("PATCH", `/api/jobs/${jobId}/resume/${resumeId}`, { content }),
  resumePdfUrl: (jobId, resumeId) => `/api/jobs/${jobId}/resume/${resumeId}/pdf`,
  promoteToProfile: (jobId, resumeId, promote) =>
    API._req("POST", `/api/jobs/${jobId}/resume/${resumeId}/promote-to-profile`, { promote }),
};
