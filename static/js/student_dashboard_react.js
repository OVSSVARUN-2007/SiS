(function () {
  const rootEl = document.getElementById("student-dashboard-react");
  const dataEl = document.getElementById("student-dashboard-data");
  if (!rootEl || !dataEl || !window.React || !window.ReactDOM) {
    return;
  }

  const React = window.React;
  const ReactDOM = window.ReactDOM;
  const data = JSON.parse(dataEl.textContent || "{}");

  const e = React.createElement;

  function MetricCard(props) {
    return e(
      "div",
      { className: "react-metric-card" },
      e("span", { className: "react-metric-label" }, props.label),
      e("strong", { className: "react-metric-value" }, String(props.value))
    );
  }

  function RequestItem(props) {
    return e(
      "div",
      { className: "react-list-item" },
      e("div", { className: "react-list-head" }, props.title),
      e(
        "div",
        { className: "react-list-meta" },
        props.category + " | " + props.status + (props.remark ? " | " + props.remark : "")
      )
    );
  }

  function AssignmentItem(props) {
    return e(
      "div",
      { className: "react-list-item" },
      e("div", { className: "react-list-head" }, props.title),
      e(
        "div",
        { className: "react-list-meta" },
        (props.submitted ? "Submitted" : "Pending") + (props.dueDate ? " | Due " + props.dueDate : "")
      )
    );
  }

  function DashboardApp() {
    const attendance = Number(data.attendancePercentage || 0);
    const ringStyle = { background: "conic-gradient(var(--primary-2) 0 " + attendance + "%, rgba(127,155,199,0.18) " + attendance + "% 100%)" };

    return e(
      "section",
      { className: "react-dashboard-grid" },
      e(
        "div",
        { className: "react-hero-card" },
        e("div", { className: "react-kicker" }, "Advanced Student View"),
        e("h2", { className: "react-title" }, "Your portal, organized around what needs attention"),
        e(
          "p",
          { className: "react-copy" },
          data.studentName + " | " + (data.department || "-") + " | Year " + (data.academicYear || "-") + " | Section " + (data.section || "-")
        ),
        e(
          "div",
          { className: "react-metric-row" },
          (data.stats || []).map(function (item, index) {
            return e(MetricCard, { key: index, label: item.label, value: item.value });
          })
        )
      ),
      e(
        "div",
        { className: "react-attendance-card" },
        e("div", { className: "react-kicker" }, "Attendance Health"),
        e(
          "div",
          { className: "react-ring", style: ringStyle },
          e("div", { className: "react-ring-inner" }, e("strong", null, attendance + "%"))
        ),
        e("p", { className: "react-copy small" }, attendance < 75 ? "Needs attention for eligibility-related workflows." : "Attendance is in a healthier range.")
      ),
      e(
        "div",
        { className: "react-panel-card" },
        e("div", { className: "react-panel-title" }, "Latest Requests"),
        (data.requests && data.requests.length)
          ? data.requests.map(function (item) {
              return e(RequestItem, {
                key: item.id,
                title: item.title,
                category: item.category,
                status: item.status,
                remark: item.remark
              });
            })
          : e("div", { className: "react-empty" }, "No requests yet.")
      ),
      e(
        "div",
        { className: "react-panel-card" },
        e("div", { className: "react-panel-title" }, "Assignment Focus"),
        (data.assignments && data.assignments.length)
          ? data.assignments.map(function (item) {
              return e(AssignmentItem, {
                key: item.id,
                title: item.title,
                dueDate: item.dueDate,
                submitted: item.submitted
              });
            })
          : e("div", { className: "react-empty" }, "No assignments available.")
      )
    );
  }

  ReactDOM.createRoot(rootEl).render(e(DashboardApp));
})();
