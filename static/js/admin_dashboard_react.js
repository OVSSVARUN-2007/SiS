(function () {
  const rootEl = document.getElementById("admin-dashboard-react");
  const dataEl = document.getElementById("admin-dashboard-data");
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

  function StreamItem(props) {
    return e(
      "div",
      { className: "react-list-item" },
      e("div", { className: "react-list-head" }, props.title),
      e("div", { className: "react-list-meta" }, props.meta)
    );
  }

  function DashboardApp() {
    return e(
      "section",
      { className: "react-dashboard-grid admin" },
      e(
        "div",
        { className: "react-hero-card" },
        e("div", { className: "react-kicker" }, "Advanced Admin View"),
        e("h2", { className: "react-title" }, "Review campus operations from one surface"),
        e("p", { className: "react-copy" }, "Approval flow, student visibility, and recent operational signals for " + (data.adminName || "Admin")),
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
        { className: "react-panel-card" },
        e("div", { className: "react-panel-title" }, "Approval Queue"),
        (data.requests && data.requests.length)
          ? data.requests.map(function (item) {
              return e(StreamItem, {
                key: item.id,
                title: item.studentName + " | " + item.title,
                meta: item.category + " | " + item.status + (item.remark ? " | " + item.remark : "")
              });
            })
          : e("div", { className: "react-empty" }, "No requests in the queue.")
      ),
      e(
        "div",
        { className: "react-panel-card" },
        e("div", { className: "react-panel-title" }, "Students Snapshot"),
        (data.students && data.students.length)
          ? data.students.map(function (item) {
              return e(StreamItem, {
                key: item.id,
                title: item.name,
                meta: item.department + " | Year " + item.academicYear + " | Section " + item.section
              });
            })
          : e("div", { className: "react-empty" }, "No students found.")
      )
    );
  }

  ReactDOM.createRoot(rootEl).render(e(DashboardApp));
})();
