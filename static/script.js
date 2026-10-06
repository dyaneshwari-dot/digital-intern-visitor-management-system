document.addEventListener("DOMContentLoaded", () => {
    // Auto-hide flash messages.
    setTimeout(() => {
        document.querySelectorAll(".alert").forEach(el => {
            el.style.opacity = "0";
            setTimeout(() => el.remove(), 500);
        });
    }, 4500);

    const dateInput = document.getElementById("visitDate");
    const slotList = document.getElementById("slotList");
    const selectedSlot = document.getElementById("selectedSlot");
    const startInput = document.getElementById("startTime");
    const endInput = document.getElementById("endTime");
    const confirmBtn = document.getElementById("confirmBtn");
    const slotDateLabel = document.getElementById("slotDateLabel");

    if (!dateInput || !slotList) return;

    const loadSlots = async () => {
        const chosenDate = dateInput.value;
        slotDateLabel.textContent = chosenDate;

        try {
            const response = await fetch(`${slotsUrl}?date=${encodeURIComponent(chosenDate)}`);
            const slots = await response.json();

            slotList.innerHTML = "";

            slots.forEach(slot => {
                const button = document.createElement("button");
                button.type = "button";
                button.className = `slot ${slot.available ? "available" : "booked"}`;
                button.disabled = !slot.available;
                button.innerHTML = `
                    <span class="dot ${slot.available ? "green" : "red"}"></span>
                    <span>${slot.start} - ${slot.end}</span>
                    <strong>${slot.available ? "Available" : "Booked"}</strong>
                    ${slot.available ? "" : `<small>(${slot.name})</small>`}
                `;

                if (slot.available) {
                    button.dataset.start = slot.start;
                    button.dataset.end = slot.end;

                    button.addEventListener("click", () => {
                        document.querySelectorAll(".slot.available").forEach(s => s.classList.remove("selected"));
                        button.classList.add("selected");
                        startInput.value = slot.start;
                        endInput.value = slot.end;
                        selectedSlot.textContent = `Selected: ${slot.start} - ${slot.end}`;
                        confirmBtn.disabled = false;
                    });
                }

                slotList.appendChild(button);
            });
        } catch (error) {
            slotList.innerHTML = "<p class='muted'>Could not load slots. Check the server.</p>";
        }
    };

    dateInput.addEventListener("change", loadSlots);
});
