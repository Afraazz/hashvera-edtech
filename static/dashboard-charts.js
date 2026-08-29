(() => {
    // Premium Color Palette
    const palette = ["#6366f1", "#10b981", "#f59e0b", "#3b82f6", "#ef4444", "#8b5cf6", "#ec4899"];

    function getCssColor(variableName, fallback) {
        const value = getComputedStyle(document.body).getPropertyValue(variableName).trim();
        return value || fallback;
    }

    function setupCanvas(canvas) {
        if (!canvas) {
            return null;
        }

        const rect = canvas.getBoundingClientRect();
        const ratio = window.devicePixelRatio || 1;
        const width = Math.max(280, Math.floor(rect.width || canvas.clientWidth || 320));
        const height = Math.max(220, Math.floor(rect.height || canvas.clientHeight || 260));

        canvas.width = Math.round(width * ratio);
        canvas.height = Math.round(height * ratio);

        const ctx = canvas.getContext("2d");
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        ctx.clearRect(0, 0, width, height);

        return { ctx, width, height };
    }

    function drawRoundedRect(ctx, x, y, width, height, radius) {
        const safeRadius = Math.max(0, Math.min(radius, width / 2, height / 2));
        ctx.beginPath();
        ctx.moveTo(x + safeRadius, y);
        ctx.arcTo(x + width, y, x + width, y + height, safeRadius);
        ctx.arcTo(x + width, y + height, x, y + height, safeRadius);
        ctx.arcTo(x, y + height, x, y, safeRadius);
        ctx.arcTo(x, y, x + width, y, safeRadius);
        ctx.closePath();
    }

    function drawLegend(ctx, width, height, labels, values, colors, options = {}) {
        const textColor = getCssColor("--text-muted", "#64748b");
        const columns = options.columns || (width >= 360 && labels.length > 2 ? 2 : 1);
        const rows = Math.ceil(labels.length / columns);
        const itemHeight = options.itemHeight || 24;
        const columnWidth = (width - 64) / columns;
        const startX = options.startX || 42;
        const startY = options.startY || height - (rows * itemHeight) - 16;

        ctx.font = "600 12px 'Outfit', sans-serif";
        ctx.textBaseline = "middle";
        ctx.textAlign = "left";

        labels.forEach((label, index) => {
            const item = `${label}: ${values[index]}`;
            const column = index % columns;
            const row = Math.floor(index / columns);
            const x = startX + (column * columnWidth);
            const y = startY + (row * itemHeight);

            ctx.fillStyle = colors[index % colors.length];
            ctx.beginPath();
            ctx.arc(x + 6, y, 5, 0, Math.PI * 2);
            ctx.fill();

            ctx.fillStyle = textColor;
            ctx.fillText(item, x + 18, y);
        });
    }

    function drawBarChart(canvas, labels, values, colors) {
        const setup = setupCanvas(canvas);
        if (!setup) {
            return;
        }

        const { ctx, width, height } = setup;
        const textColor = getCssColor("--text-main", "#0f172a");
        const axisColor = getCssColor("--line", "rgba(15, 23, 42, 0.08)");
        const maxValue = Math.max(...values, 1);
        const chartLeft = 30;
        const chartTop = 20;
        const chartBottom = height - 60;
        const chartHeight = chartBottom - chartTop;
        const slotWidth = (width - chartLeft - 24) / Math.max(values.length, 1);
        const barWidth = Math.min(44, Math.max(20, slotWidth * 0.56));

        // Draw horizontal grid lines
        ctx.strokeStyle = axisColor;
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 5]);
        for (let i = 0; i <= 4; i++) {
            const y = chartBottom - (i * chartHeight / 4);
            ctx.beginPath();
            ctx.moveTo(chartLeft, y);
            ctx.lineTo(width - 16, y);
            ctx.stroke();
        }
        ctx.setLineDash([]);

        ctx.font = "700 11px 'Outfit', sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "top";

        values.forEach((value, index) => {
            const x = chartLeft + (slotWidth * index) + ((slotWidth - barWidth) / 2);
            const barHeight = (value / maxValue) * (chartHeight - 12);
            const y = chartBottom - barHeight;
            const color = colors[index % colors.length];

            // Draw Bar Shadow
            ctx.shadowColor = "rgba(0,0,0,0.05)";
            ctx.shadowBlur = 10;
            ctx.shadowOffsetY = 4;

            // Bar Gradient
            const gradient = ctx.createLinearGradient(x, y, x, chartBottom);
            gradient.addColorStop(0, color);
            gradient.addColorStop(1, color + "CC"); // Add transparency for gradient

            ctx.fillStyle = gradient;
            drawRoundedRect(ctx, x, y, barWidth, barHeight, 10);
            ctx.fill();

            // Reset Shadow
            ctx.shadowColor = "transparent";
            ctx.shadowBlur = 0;
            ctx.shadowOffsetY = 0;

            ctx.fillStyle = textColor;
            ctx.fillText(String(value), x + (barWidth / 2), y - 18);
            
            // Use horizontal labels (straight)
            ctx.fillStyle = getCssColor("--text-muted", "#64748b");
            ctx.font = "600 11px 'Outfit', sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "top";
            
            // Truncate based on slot width to prevent overlap
            let label = labels[index];
            const maxLabelWidth = slotWidth - 10;
            let measured = ctx.measureText(label).width;
            
            if (measured > maxLabelWidth) {
                // Aggressive truncation for horizontal fit
                while (measured > maxLabelWidth && label.length > 3) {
                    label = label.substring(0, label.length - 1);
                    measured = ctx.measureText(label + "...").width;
                }
                label += "...";
            }
            
            ctx.fillText(label, x + (barWidth / 2), chartBottom + 10);
        });
    }

    function drawGroupedBarChart(canvas, labels, seriesList, colors) {
        const setup = setupCanvas(canvas);
        if (!setup) {
            return;
        }

        const { ctx, width, height } = setup;
        const textColor = getCssColor("--text-main", "#0f172a");
        const axisColor = getCssColor("--line", "rgba(15, 23, 42, 0.08)");
        const flattened = seriesList.flatMap((series) => series.values || []);
        const maxValue = Math.max(...flattened, 1);
        const chartLeft = 36;
        const chartTop = 20;
        const chartBottom = height - 110;
        const chartHeight = chartBottom - chartTop;
        const slotWidth = (width - chartLeft - 24) / Math.max(labels.length, 1);
        const seriesCount = Math.max(seriesList.length, 1);
        const barWidth = Math.min(28, Math.max(12, (slotWidth * 0.72) / seriesCount));

        ctx.strokeStyle = axisColor;
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 5]);
        for (let i = 0; i <= 4; i++) {
            const y = chartBottom - (i * chartHeight / 4);
            ctx.beginPath();
            ctx.moveTo(chartLeft, y);
            ctx.lineTo(width - 16, y);
            ctx.stroke();
        }
        ctx.setLineDash([]);

        ctx.font = "700 11px 'Outfit', sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "top";

        labels.forEach((label, index) => {
            const groupWidth = barWidth * seriesCount;
            const groupX = chartLeft + (slotWidth * index) + ((slotWidth - groupWidth) / 2);

            seriesList.forEach((series, seriesIndex) => {
                const value = series.values[index] || 0;
                const barHeight = (value / maxValue) * (chartHeight - 12);
                const x = groupX + (seriesIndex * barWidth);
                const y = chartBottom - barHeight;
                const color = colors[seriesIndex % colors.length];

                ctx.fillStyle = color;
                drawRoundedRect(ctx, x, y, barWidth - 2, barHeight, 8);
                ctx.fill();
            });

            ctx.fillStyle = getCssColor("--text-muted", "#64748b");
            ctx.fillText(label, chartLeft + (slotWidth * index) + (slotWidth / 2), chartBottom + 10);
        });

        const legendLabels = seriesList.map((series) => series.label);
        const legendValues = seriesList.map((series) => {
            return (series.values || []).reduce((sum, value) => sum + value, 0);
        });
        drawLegend(ctx, width, height, legendLabels, legendValues, colors);
    }

    function drawSegmentChart(canvas, labels, values, colors, innerRadiusRatio) {
        const setup = setupCanvas(canvas);
        if (!setup) {
            return;
        }

        const { ctx, width, height } = setup;
        const total = values.reduce((sum, value) => sum + value, 0);
        const legendColumns = width >= 390 && labels.length > 2 ? 2 : 1;
        const legendRows = Math.ceil(labels.length / legendColumns);
        const legendItemHeight = 23;
        const legendHeight = legendRows * legendItemHeight;
        const legendStartY = Math.max(138, height - legendHeight - 14);
        const chartTop = 18;
        const chartBottom = Math.max(112, legendStartY - 18);
        const chartHeight = chartBottom - chartTop;
        const centerX = width / 2;
        const centerY = chartTop + (chartHeight / 2);
        const radius = Math.max(34, Math.min(width * 0.2, chartHeight * 0.46, 62));
        const innerRadius = radius * innerRadiusRatio;
        const textColor = getCssColor("--text-main", "#0f172a");

        if (!total) {
            ctx.fillStyle = textColor;
            ctx.font = "600 14px 'Outfit', sans-serif";
            ctx.textAlign = "center";
            ctx.fillText("No data available", centerX, centerY);
            return;
        }

        let startAngle = -Math.PI / 2;

        values.forEach((value, index) => {
            const slice = (value / total) * Math.PI * 2;
            const endAngle = startAngle + slice;
            const color = colors[index % colors.length];

            // Segment Gradient
            const gradX = centerX + Math.cos(startAngle + slice/2) * radius;
            const gradY = centerY + Math.sin(startAngle + slice/2) * radius;
            const gradient = ctx.createRadialGradient(centerX, centerY, innerRadius, centerX, centerY, radius);
            gradient.addColorStop(0, color);
            gradient.addColorStop(1, color + "DD");

            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.moveTo(centerX, centerY);
            ctx.arc(centerX, centerY, radius, startAngle, endAngle);
            ctx.closePath();
            ctx.fill();

            // Segment Border
            ctx.strokeStyle = getCssColor("--panel-strong", "#ffffff");
            ctx.lineWidth = 2;
            ctx.stroke();

            startAngle = endAngle;
        });

        if (innerRadius > 0) {
            ctx.fillStyle = getCssColor("--panel-strong", "#ffffff");
            ctx.beginPath();
            ctx.arc(centerX, centerY, innerRadius, 0, Math.PI * 2);
            ctx.fill();

            ctx.fillStyle = textColor;
            ctx.font = "800 24px 'Outfit', sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(String(total), centerX, centerY - 4);

            ctx.fillStyle = getCssColor("--text-muted", "#64748b");
            ctx.font = "600 11px 'Outfit', sans-serif";
            ctx.fillText("TOTAL", centerX, centerY + 18);
        }

        drawLegend(ctx, width, height, labels, values, colors, {
            columns: legendColumns,
            itemHeight: legendItemHeight,
            startY: legendStartY,
        });
    }

    function renderCharts() {
        const chartData = window.dashboardChartData;
        if (!chartData) {
            return;
        }

        drawBarChart(
            document.getElementById("overviewChart"),
            chartData.overview_labels || [],
            chartData.overview_values || [],
            ["#6366f1", "#10b981", "#f59e0b", "#3b82f6", "#ef4444"]
        );

        drawSegmentChart(
            document.getElementById("typeChart"),
            chartData.type_labels || [],
            chartData.type_values || [],
            ["#8b5cf6", "#ec4899", "#f59e0b", "#10b981", "#6366f1"],
            0.55
        );

        drawSegmentChart(
            document.getElementById("roleChart"),
            chartData.role_labels || [],
            chartData.role_values || [],
            ["#3b82f6", "#10b981", "#f59e0b", "#ef4444"],
            0.55
        );

        drawBarChart(
            document.getElementById("courseChart"),
            chartData.course_labels || [],
            chartData.course_values || [],
            ["#10b981", "#6366f1", "#3b82f6", "#f59e0b", "#8b5cf6"]
        );

        drawGroupedBarChart(
            document.getElementById("trendChart"),
            chartData.trend_labels || [],
            [
                { label: "Minted", values: chartData.trend_added_values || [] },
                { label: "Archived", values: chartData.trend_archived_values || [] },
            ],
            ["#10b981", "#ef4444"]
        );

        drawBarChart(
            document.getElementById("activityChart"),
            chartData.activity_labels || [],
            chartData.activity_values || [],
            ["#6366f1", "#10b981", "#f59e0b", "#3b82f6", "#ef4444"]
        );
    }

    function scheduleRenderCharts() {
        if ("requestIdleCallback" in window) {
            window.requestIdleCallback(renderCharts, { timeout: 1200 });
            return;
        }
        window.setTimeout(renderCharts, 120);
    }

    window.renderDashboardCharts = scheduleRenderCharts;
    document.addEventListener("DOMContentLoaded", scheduleRenderCharts);
    window.addEventListener("resize", () => {
        window.clearTimeout(window.dashboardChartResizeTimer);
        window.dashboardChartResizeTimer = window.setTimeout(renderCharts, 120);
    });
})();
