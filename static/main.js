const SOCKET_URL = "ws://localhost:8000/ws"

const ELEMENT_TYPE_TEXT = "text";
const ELEMENT_TYPE_INT = "int";
const ELEMENT_TYPE_FLOAT = "float";
const ELEMENT_TYPE_BOOL = "bool";


const PlotSettings = ({ range, rangeUpdated }) => {
    return React.createElement(
        "select",
        { value: range, onChange: (event) => rangeUpdated(event.target.value) },
        [
            React.createElement("option", { value: "-5m", key: "-5m" }, "last 5 minutes"),
            React.createElement("option", { value: "-30m", key: "-30m" }, "last 30 minutes"),
            React.createElement("option", { value: "-1h", key: "-1h" }, "last hour"),
            React.createElement("option", { value: "-12h", key: "-12h" }, "last 12 hours"),
            React.createElement("option", { value: "-1d", key: "-1d" }, "last day"),
            React.createElement("option", { value: "-7d", key: "-7d" }, "last week"),
            React.createElement("option", { value: "-30d", key: "-30d" }, "last month"),
        ],
    );
};

const PlotRenderer = ({ scheme_id, element }) => {

    const [range, setRange] = React.useState("-1h");
    const [fluxResponse, setFluxResponse] = React.useState("");

    React.useEffect(() => {
        (async () => {
            try {
                const response = await fetch(`http://localhost:8000/schemes/${SCHEME_CONFIG.scheme_id}/influx/${element.svg_id}?range=${range}`);
                const data = await response.text();
                console.log(data);
                setFluxResponse(data);
            } catch (error) {
                console.error(error)
            }
        })();
    }, [scheme_id, element, range, setFluxResponse]);

    const style = {
        width: "calc(100vw - 5rem)",
        height: "calc(70vh - 20px)",
        margin: "1rem",
        background: "#333333",
    };

    const lineLayer = React.useMemo(() => ({
        type: "line",
        x: "_time",
        y: "_value"
    }), []);

    const config = React.useMemo(() => ({ fluxResponse, layers: [lineLayer] }), [fluxResponse]);

    return React.createElement("div", {}, [
        React.createElement(PlotSettings, { rangeUpdated: (range) => setRange(range), key: "graphOptions" }, null),
        React.createElement("div", {style, key: "graph"}, React.createElement(Giraffe.Plot, {config}, null)),
    ]);
};

// class PlotRenderer extends React.Component {
//     render() {
//         const style = {
//             width: "calc(100vw - 5rem)",
//             height: "calc(70vh - 20px)",
//             margin: "1rem",
//         };

//         const lineLayer = {
//             type: "line",
//             x: "_time",
//             y: "_value"
//         };

//         const config = {
//             fluxResponse: this.props.fluxResponse,
//             layers: [lineLayer]
//         };

//         const SimplePlot = React.createElement(Giraffe.Plot, {config}, null);
//         return React.createElement('div', {style}, SimplePlot);
//     }
// }


const renderValue = (dataModule, dataId, data) => {
    const element = SCHEME_CONFIG.elements
        .find((el) => el.data_module === dataModule && el.data_id === dataId);
    if (!element) return;
    const svg_element = document.querySelector(`#scheme svg #${element.svg_id}`);
    if (!svg_element) return;
    switch (element.type) {
        case ELEMENT_TYPE_TEXT:
            svg_element.innerHTML = (data instanceof Array
                ? data.map((v) => element.map[v] ?? v) : element.map[data] ?? data).toString();
            break;
        case ELEMENT_TYPE_INT:
            svg_element.innerHTML = data.toString();
            break;
        case ELEMENT_TYPE_FLOAT:
            svg_element.innerHTML = (data instanceof Array
                ? data.map((v) => Number.parseFloat(v).toFixed(element.precision))
                : Number.parseFloat(data).toFixed(element.precision)).toString();
            break;
        case ELEMENT_TYPE_BOOL:
            const value = element.true_values.find((tv) => tv.toString() === data.toString());
            svg_element.innerHTML = value ? element.true_text : element.false_text;
            svg_element.style.fill = value ? element.true_fill : element.false_fill;
    }
};


const aggregateElements = (elements)  => {
    aggregated = {}
    for (const element of elements) {
        if (!aggregated[element.data_module])
            aggregated[element.data_module] = [];
        aggregated[element.data_module].push(element);
    }
    return aggregated;
};

const showMenu = (element, socket) => {
    document.querySelector("#update-value").value = "";
    document.querySelector("#menu").classList.remove("menu-hidden");
    const message = document.querySelector("#update-message");
    const oldSubmit = document.querySelector("#update-submit");
    oldSubmit.replaceWith(oldSubmit.cloneNode(true));
    const submit = document.querySelector("#update-submit");
    if (element.write) {
        submit.removeAttribute("disabled");
    } else {
        submit.setAttribute("disabled", true);
    }
    submit.addEventListener("click", () => {
        const value = document.querySelector("#update-value").value;
        switch (element.type) {
            case ELEMENT_TYPE_TEXT:
                if (element.enum && element.enum.length()
                        && !element.enum.find((v) => v === value)) {
                    message.innerHTML = `Value is not one of ${element.enum}`;
                    return;
                }
                if (element.match && !new RegExp(element).test(value)) {
                    message.innerHTML = `Value is does not match '${element.match}'`;
                    return;
                }
                break;
            case ELEMENT_TYPE_INT:
                const intValue = Number.parseInt(value);
                if (isNaN(intValue)) {
                    message.innerHTML = "Value is not a number";
                    return;
                }
                if (element.min !== null && element.min > intValue) {
                    message.innerHTML = `Value is less than ${element.min}`
                    return;
                }
                if (element.max !== null && element.max < intValue) {
                    message.innerHTML = `Value is more than ${element.max}`
                    return;
                }
                break;
            case ELEMENT_TYPE_FLOAT:
                const floatValue = Number.parseInt(value);
                if (isNaN(floatValue)) {
                    message.innerHTML = "Value is not a number";
                    return;
                }
                if (element.min !== null && element.minf > floatValue) {
                    message.innerHTML = `Value is less than ${element.min}`
                    return;
                }
                if (element.max !== null && element.maxf < floatValue) {
                    message.innerHTML = `Value is more than ${element.max}`
                    return;
                }
                break;
            case ELEMENT_TYPE_BOOL:
                if (element.enum && element.enum.length()
                        && !element.enum.find((v) => v === value)) {
                    message.innerHTML = `Value is not one of ${element.enum}`;
                    return;
                }
                break;
        }
        socket.send(JSON.stringify({ command: "set", data: { [element.data_id]: value }}));
        document.querySelector("#update-value").value = "";
    });

    ReactDOM.render(
        React.createElement(PlotRenderer, {
            scheme_id: SCHEME_CONFIG.scheme_id,
            element,
        }, null),
        document.getElementById("graph"),
    );
};

const initialize = () => {
    const aggregated = aggregateElements(SCHEME_CONFIG.elements);
    for (const dataModule of Object.keys(aggregated)) {
        const socket = new WebSocket(`${SOCKET_URL}/${dataModule}`);
        socket.addEventListener(
            "error",
            (ev) => console.error(`Websocker error for ${dataModule}`, ev),
        );
        socket.addEventListener("message", (ev) => {
            const msg = JSON.parse(ev.data);
            // console.log(msg);
            if (msg.status) {
                if (msg.status >= 400) {
                    console.error(msg);
                } else {
                    console.log(msg);
                }
            } else {
                for (const dataId in msg) {
                    renderValue(dataModule, dataId, msg[dataId]);
                }
            }
        });
        socket.addEventListener("open", () => {
            const cov = aggregated[dataModule]
                .filter((element) => element.cov || SCHEME_CONFIG.cov);
            const interval = aggregated[dataModule]
                .filter((element) => !element.cov && !SCHEME_CONFIG.cov);
            socket.send(JSON.stringify({
                command: "cov",
                data_ids: cov.map((element) => element.data_id),
            }));
            setInterval(() => socket.send(JSON.stringify({
                command: "get",
                data_ids: interval.map((element) => element.data_id),
            })), SCHEME_CONFIG.interval * 1000);
        });

        for (const element of aggregated[dataModule]) {
            const svg_element = document.querySelector(`#scheme svg #${element.svg_id}`);
            svg_element.addEventListener("click", () => showMenu(element, socket));
            svg_element.style.cursor = "pointer";
        }
    }
};


initialize();
