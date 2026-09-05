const $ = (id) => document.getElementById(id);
let sessionId = null, lessonId = null, quizId = null, currentLesson = null, currentQuiz = null;

fetch("/api/status").then(r => r.json()).then(d => {
  $("provider-badge").textContent = `LLM backend: ${d.llm_provider}`;
});

$("file-input").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  $("upload-status").textContent = "Uploading & indexing (building RAG knowledge base)...";
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch("/api/upload", { method: "POST", body: fd });
  const data = await res.json();
  if (data.error) { $("upload-status").textContent = "Error: " + data.error; return; }
  sessionId = data.session_id;
  let statusMsg = `Indexed ${data.chunk_count} chunks. Key concepts detected: ${data.top_concepts.join(", ")}`;
  if (data.ocr_chunks_found > 0) {
    statusMsg += ` (including text OCR'd from ${data.ocr_chunks_found} image/diagram/scanned-page chunk(s))`;
  }
  $("upload-status").textContent = statusMsg;
});

$("plan-btn").addEventListener("click", async () => {
  $("plan-btn").disabled = true;
  $("plan-btn").textContent = "Planning lesson...";
  const body = {
    topic: $("topic-input").value.trim(),
    level: $("level-select").value,
    minutes: parseInt($("minutes-select").value),
    language: $("language-select").value,
    session_id: sessionId,
  };
  try {
    const res = await fetch("/api/lesson/plan", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const lesson = await res.json();
    if (lesson.error) throw new Error(lesson.error);
    currentLesson = lesson;
    lessonId = lesson.lesson_id;
    renderLesson(lesson);
    $("lesson-card").classList.remove("hidden");
    $("quiz-card").classList.remove("hidden");
    $("lesson-card").scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    alert("Could not generate lesson: " + err.message);
  } finally {
    $("plan-btn").disabled = false;
    $("plan-btn").textContent = "Generate Lesson Plan";
  }
});

function renderLesson(lesson) {
  $("lesson-title").textContent = `2. ${lesson.title || "Your Lesson"}`;
  $("objectives").innerHTML = "<b>Objectives:</b> " + (lesson.objectives || []).join(" · ");
  const container = $("sections");
  container.innerHTML = "";
  (lesson.sections || []).forEach((sec, idx) => {
    const div = document.createElement("div");
    div.className = "section-block";
    div.innerHTML = `
      <h3>${sec.title}</h3>
      <div>${sec.explanation}</div>
      <div class="example">Example: ${sec.example || ""}</div>
      <div class="checkpoint">
        <div><b>Checkpoint:</b> ${sec.checkpoint_question?.prompt || ""}</div>
        <textarea placeholder="Type your answer..." data-idx="${idx}"></textarea>
        <div class="answer-row">
          <button class="answer-btn" data-idx="${idx}">Submit Answer</button>
          <button class="mic-btn" data-idx="${idx}" title="Answer by voice">🎤 Answer by voice</button>
        </div>
        <div class="feedback-slot" data-idx="${idx}"></div>
      </div>`;
    container.appendChild(div);
  });
  container.querySelectorAll(".answer-btn").forEach(btn => {
    btn.addEventListener("click", () => submitAnswer(btn.dataset.idx));
  });
  container.querySelectorAll(".mic-btn").forEach(btn => {
    btn.addEventListener("click", () => toggleVoiceAnswer(btn));
  });
}

// Records a checkpoint answer with the mic (Speech-to-Text) instead of
// typing - press once to start, press again to stop and submit.
const _recorders = {};
async function toggleVoiceAnswer(btn) {
  const idx = btn.dataset.idx;
  const slot = document.querySelector(`.feedback-slot[data-idx="${idx}"]`);

  if (_recorders[idx] && _recorders[idx].state === "recording") {
    _recorders[idx].stop();
    return;
  }

  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    slot.innerHTML = `<div class="feedback other">Microphone access denied or unavailable: ${err.message}</div>`;
    return;
  }

  const recorder = new MediaRecorder(stream);
  const chunks = [];
  recorder.ondataavailable = (e) => chunks.push(e.data);
  recorder.onstop = async () => {
    stream.getTracks().forEach((t) => t.stop());
    btn.textContent = "🎤 Answer by voice";
    slot.innerHTML = `<div class="hint">Transcribing and evaluating your voice answer...</div>`;

    const blob = new Blob(chunks, { type: "audio/webm" });
    const fd = new FormData();
    fd.append("audio", blob, "answer.webm");
    fd.append("section_index", idx);

    try {
      const res = await fetch(`/api/lesson/${lessonId}/answer/audio`, { method: "POST", body: fd });
      const result = await res.json();
      if (result.error) { slot.innerHTML = `<div class="feedback other">${result.error}</div>`; return; }
      renderAnswerFeedback(slot, result, `You said: "${result.answer_text}"`);
    } catch (err) {
      slot.innerHTML = `<div class="feedback other">Voice answer failed: ${err.message}</div>`;
    }
  };

  recorder.start();
  _recorders[idx] = recorder;
  btn.textContent = "⏹ Stop & submit";
  slot.innerHTML = `<div class="hint">Recording... click again to stop.</div>`;
}

async function submitAnswer(idx) {
  const textarea = document.querySelector(`textarea[data-idx="${idx}"]`);
  const slot = document.querySelector(`.feedback-slot[data-idx="${idx}"]`);
  slot.innerHTML = `<div class="hint">Evaluating your answer...</div>`;
  const res = await fetch(`/api/lesson/${lessonId}/answer`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ section_index: parseInt(idx), answer: textarea.value }),
  });
  const result = await res.json();
  renderAnswerFeedback(slot, result);
}

function renderAnswerFeedback(slot, result, precedingLine) {
  const cls = result.correctness === "correct" ? "correct" : "other";
  let html = precedingLine ? `<div class="hint">${precedingLine}</div>` : "";
  html += `<div class="feedback ${cls}"><b>${result.correctness}</b> - ${result.feedback}</div>`;
  if (result.reexplanation) {
    html += `<div class="reexplain">
      <b>Let's re-approach this:</b> ${result.reexplanation.explanation}<br>
      <i>${result.reexplanation.new_example || ""}</i><br>
      <b>Follow-up:</b> ${result.reexplanation.followup_question || ""}
    </div>`;
  }
  slot.innerHTML = html;
}

$("video-btn").addEventListener("click", async () => {
  $("video-btn").disabled = true;
  $("video-status").textContent = "Rendering teaching video (avatar + voice + diagrams)... this can take a moment.";
  try {
    const res = await fetch(`/api/lesson/${lessonId}/video`, { method: "POST" });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    const video = $("lesson-video");
    video.src = data.video_url;
    video.classList.remove("hidden");
    $("video-status").textContent = "Video ready.";
  } catch (err) {
    $("video-status").textContent = "Video generation failed: " + err.message;
  } finally {
    $("video-btn").disabled = false;
  }
});

$("quiz-btn").addEventListener("click", async () => {
  const res = await fetch("/api/quiz/generate", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lesson_id: lessonId }),
  });
  currentQuiz = await res.json();
  quizId = currentQuiz.quiz_id;
  renderQuiz(currentQuiz);
});

function renderQuiz(quiz) {
  const body = $("quiz-body");
  body.innerHTML = "";
  quiz.questions.forEach((q) => {
    const div = document.createElement("div");
    div.className = "quiz-q";
    if (q.type === "mcq") {
      div.innerHTML = `<b>${q.prompt}</b>` + q.options.map((opt, i) =>
        `<label class="opt"><input type="radio" name="${q.id}" value="${i}"> ${opt}</label>`
      ).join("");
    } else {
      div.innerHTML = `<b>${q.prompt}</b><textarea data-qid="${q.id}" style="width:100%;margin-top:8px;"></textarea>`;
    }
    body.appendChild(div);
  });
  $("submit-quiz-btn").classList.remove("hidden");
}

$("submit-quiz-btn").addEventListener("click", async () => {
  const answers = {};
  currentQuiz.questions.forEach((q) => {
    if (q.type === "mcq") {
      const checked = document.querySelector(`input[name="${q.id}"]:checked`);
      answers[q.id] = checked ? parseInt(checked.value) : null;
    } else {
      answers[q.id] = document.querySelector(`textarea[data-qid="${q.id}"]`).value;
    }
  });
  const studentId = $("student-id").value.trim() || "guest";
  const res = await fetch(`/api/quiz/${quizId}/submit`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers, student_id: studentId }),
  });
  const report = await res.json();
  $("report").innerHTML = `
    <div class="report-box">
      <div class="score">${report.score_percent}%</div>
      <div>${(report.strong_areas || []).map(a => `<span class="tag strong">${a}</span>`).join("")}</div>
      <div>${(report.weak_areas || []).map(a => `<span class="tag weak">${a}</span>`).join("")}</div>
      <p><b>Recommendation:</b> ${report.recommendation}</p>
      <p><b>Suggested next topic:</b> ${report.suggested_next_topic}</p>
    </div>`;
  loadProfile(studentId);
});

async function loadProfile(studentId) {
  const res = await fetch(`/api/profile/${studentId}`);
  const profile = await res.json();
  $("profile-card").classList.remove("hidden");
  $("profile-body").innerHTML = `
    <p><b>Sessions completed:</b> ${profile.session_count}</p>
    <p><b>Topics studied:</b> ${profile.topics_studied.join(", ") || "-"}</p>
    <p><b>Strong concepts:</b> ${(profile.strong_concepts || []).map(a => `<span class="tag strong">${a}</span>`).join("") || "-"}</p>
    <p><b>Weak concepts:</b> ${(profile.weak_concepts || []).map(a => `<span class="tag weak">${a}</span>`).join("") || "-"}</p>
    <p><b>Recommended next:</b> ${profile.recommended_next || "-"}</p>`;
}
