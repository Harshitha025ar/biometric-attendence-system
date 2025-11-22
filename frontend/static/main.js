//--------------------------------------------------------------
//  CAMERA SETUP
//--------------------------------------------------------------

function startCamera() {
    const video = document.getElementById("videoFeed");
    if (!video) return;

    navigator.mediaDevices.getUserMedia({ video: true })
        .then(stream => video.srcObject = stream)
        .catch(err => console.error("Camera error:", err));
}

function startRegisterCamera() {
    const video = document.getElementById("registerVideo");
    if (!video) return;

    navigator.mediaDevices.getUserMedia({ video: true })
        .then(stream => video.srcObject = stream)
        .catch(err => console.error("Camera error:", err));
}



//--------------------------------------------------------------
//  REAL-TIME FACE RECOGNITION
//--------------------------------------------------------------

function startRecognitionLoop() {
    const video = document.getElementById("videoFeed");
    if (!video) return;

    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");

    setInterval(() => {
        if (video.videoWidth === 0) return;

        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        ctx.drawImage(video, 0, 0);

        canvas.toBlob(blob => {
            sendFrame(blob);
        }, "image/jpeg");
    }, 1200);
}

function sendFrame(blob) {
    const fd = new FormData();
    fd.append("frame", blob);

    fetch("/api/recognize", {
        method: "POST",
        body: fd
    })
    .then(res => res.json())
    .then(data => updateDetectedList(data.detected))
    .catch(err => console.error("Recognition error:", err));
}

// ===========================
// HOLD LAST DETECTION FOR 20 SEC
// ===========================
let lastDetectTime = 0;
let lastDetectedHTML = "<p>No faces detected</p>";
let HOLD_TIME = 20000; // 20 seconds

// ===========================
// UPDATE DETECTED LIST
// ===========================
function updateDetectedList(list) {
    const box = document.getElementById("detectedList");
    if (!box) return;

    const now = Date.now();

    if (list && list.length > 0) {
        // Store detection time
        lastDetectTime = now;

        // Build HTML for detected list
        lastDetectedHTML = "";
        list.forEach(p => {

            let message = "";

            if (p.duplicate) {
                message = `<span style="color:red; font-weight:bold;">Duplicate – Already Marked!</span>`;
            } else {
                message = `<span style="color:green; font-weight:bold;">Marked Present</span>`;
            }

            lastDetectedHTML += `
                <div class="faculty-card">
                    <strong>${p.name}</strong> (${p.department})<br>
                    Confidence: ${p.confidence.toFixed(2)}%<br>
                    ${message}
                </div>
            `;
        });

        box.innerHTML = lastDetectedHTML;
        return;
    }

    // ===============================
    // NO FACE DETECTED IN THIS FRAME
    // BUT KEEP LAST DETECTION FOR 20 SEC
    // ===============================

    if (now - lastDetectTime < HOLD_TIME) {
        box.innerHTML = lastDetectedHTML;
    } else {
        box.innerHTML = "<p>No faces detected</p>";
    }
}

//--------------------------------------------------------------
//  REGISTRATION
//--------------------------------------------------------------

let REGISTERED_FACULTY_ID = null;

function registerFaculty() {
    const code = document.getElementById("faculty_code").value.trim();
    const name = document.getElementById("name").value.trim();
    const dept = document.getElementById("department").value.trim();
    const email = document.getElementById("email").value.trim();
    const phone = document.getElementById("phone").value.trim();

    if (!code || !name || !dept) {
        alert("Faculty Code, Name and Department are required!");
        return;
    }

    const fd = new FormData();
    fd.append("faculty_code", code);
    fd.append("name", name);
    fd.append("department", dept);
    fd.append("email", email);
    fd.append("phone", phone);

    fetch("/api/faculty/register", {
        method: "POST",
        body: fd
    })
    .then(res => res.json())
    .then(data => {
        REGISTERED_FACULTY_ID = data.faculty_id;
        alert("Faculty registered! Now capture images.");
    })
    .catch(err => console.error("Registration error:", err));
}



//--------------------------------------------------------------
//  UPLOAD TRAINING IMAGES
//--------------------------------------------------------------

function captureImage() {
    if (!REGISTERED_FACULTY_ID) {
        alert("Register faculty first!");
        return;
    }

    const video = document.getElementById("registerVideo");
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0);

    canvas.toBlob(blob => {
        const fd = new FormData();
        fd.append("image", blob);

        fetch(`/api/faculty/${REGISTERED_FACULTY_ID}/upload_image`, {
            method: "POST",
            body: fd
        })
        .then(res => res.json())
        .then(() => {
            let c = parseInt(document.getElementById("imgCount").innerText);
            document.getElementById("imgCount").innerText = c + 1;
        })
        .catch(err => console.error("Upload error:", err));
    }, "image/jpeg");
}



//--------------------------------------------------------------
//  DAILY ATTENDANCE REPORTS (TABLE FORMAT)
//--------------------------------------------------------------

function loadReport() {
    fetch("/api/reports/today")
        .then(res => res.json())
        .then(data => fillReport(data))
        .catch(err => console.error("Report loading error:", err));
}

function fillReport(data) {
    document.getElementById("presentCount").innerText = data.present_count;
    document.getElementById("absentCount").innerText = data.absent_count;

    const pList = document.getElementById("presentList");
    const aList = document.getElementById("absentList");

    pList.innerHTML = "";
    aList.innerHTML = "";

    // PRESENT
    if (data.present.length === 0) {
        pList.innerHTML = `<tr><td colspan="6">No one present today.</td></tr>`;
    } else {
        data.present.forEach(f => {
            pList.innerHTML += `
                <tr>
                    <td>${f.faculty_name}</td>
                    <td>${f.faculty_department}</td>
                    <td>${f.date}</td>
                    <td>${f.arrival_time}</td>
                    <td>${f.status}</td>
                    <td>${f.late_by_minutes}</td>
                </tr>
            `;
        });
    }

    // ABSENT
    if (data.absent.length === 0) {
        aList.innerHTML = `<tr><td colspan="2">No absentees today.</td></tr>`;
    } else {
        data.absent.forEach(f => {
            aList.innerHTML += `
                <tr>
                    <td>${f.name}</td>
                    <td>${f.department}</td>
                </tr>
            `;
        });
    }
}
