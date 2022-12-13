const SOCKET_URL = "ws://localhost:8000/ws";

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
                const response = await fetch(`http://localhost:8000/schemes/${SCHEME_CONFIG.scheme_id}/influx/${element.svg_id}?limit=${range}`);
                if (response.status == 200) {
                    const data = await response.text();
                    setFluxResponse(data);
                }
            } catch (error) {
                console.error(error);
                alert("Could not load data from InfluxDB");
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
        y: "_value",
    }), []);

    const config = React.useMemo(() => ({ fluxResponse, layers: [lineLayer] }), [fluxResponse]);

    return React.createElement("div", {}, [
        React.createElement("h2", {  key: "plotTitle" }, "History"),
        React.createElement(PlotSettings, { range, rangeUpdated: (range) => setRange(range), key: "plotSettings" }, null),
        fluxResponse
            ? React.createElement("div", {style, key: "plot"}, React.createElement(Giraffe.Plot, {config}, null))
            : React.createElement("div", {key: "plotLoading"}, "Loading plot data..."),
    ]);
};

const UpdateForm = ({ element, socket }) => {

    const [value, setValue] = React.useState(element.enum && element.enum.length ? element.enum[0] : "");

    const valueError = React.useMemo(() => {
        if (element.enum && element.enum.length && !element.enum.find((v) => v !== value.toString()))
            return `Value is not one of ${element.enum}`;
        if (element.match && !new RegExp(element).test(value))
            return `Value does not match ${element.match}`;
        if (element.type === ELEMENT_TYPE_FLOAT || element.type === ELEMENT_TYPE_INT) {
            const numValue = element.type === ELEMENT_TYPE_FLOAT ? Number.parseFloat(value) : Number.parseInt(value);
            if (isNaN(numValue))
                return "Value is not a number";
            if (element.min !== null && element.min > intValue)
                return `Value is less than ${element.min}`;
            if (element.max !== null && element.max < intValue)
                return `Value is more than ${element.max}`;
        }
        return null;
    }, [element, value]);

    return React.createElement("div", { className: "menu__update" }, [
        React.createElement("h2", { key: "title" }, "Update value"),
        element.enum && element.enum.length
            ? React.createElement(
                "select",
                { key: "select", value, onChange: (event) => setValue(event.target.value) },
                element.enum.map((enumValue) => React.createElement(
                    "option",
                    { key: enumValue, value: enumValue },
                    element.map[enumValue] ?? enumValue,
                )),
            )
            : React.createElement(
                "input",
                { key: "input", value, onChange: (event) => setValue(event.target.value) },
                null,
            ),
        React.createElement(
            "button",
            {
                key: "submit",
                disabled: !!valueError,
                onClick: () => {
                    socket.send(JSON.stringify({ command: "set", data: { [element.data_id]: value }}));
                    setValue(element.enum && element.enum.length ? element.enum[0] : "");
                },
            },
            "Update",
        ),
        valueError ? React.createElement("div", { key: "valueError" }, valueError) : null,
    ]);
};


const renderValue = (dataModule, dataId, data) => {
    const element = SCHEME_CONFIG.element.find((el) => el.data_module === dataModule && el.data_id === dataId);
    if (!element)
        return;
    const svgElement = document.querySelector(`#scheme svg #${element.svg_id}`);
    if (!svgElement)
        return;

    const elementStyle = element.style.find((style) => {
        const numData = Number.parseFloat(data);
        if ((style.min === null && style.max === null) || numData === NaN)
            return new RegExp(style.match).test(data)
        if (style.min !== null && numData < style.min)
            return false;
        if (style.max !== null && style.max < numData)
            return false;
        return true;
    });

    if (!elementStyle)
        return;

    if (element.type == ELEMENT_TYPE_FLOAT) {
        const numData = Number.parseFloat(data);
        if (numData !== NaN)
            data = numData.toFixed(element.precision);
    }

    if (elementStyle.fill !== null)
        svgElement.style.fill = elementStyle.fill;
    if (elementStyle.opacity !== null)
        svgElement.style.opacity = elementStyle.opacity;
    if (elementStyle.style !== null)
        svgElement.setAttribute("style", elementStyle.style);
    if (elementStyle.text !== null) {
        if (svgElement.children.length)
            svgElement.children[0].innerHTML = elementStyle.text.replace("%%", element.map[data] ?? data);
        else
            svgElement.innerHTML = elementStyle.text.replace("%%", element.map[data] ?? data);
    }
};

const showMenu = (element, socket) => {
    document.querySelector("#menu").classList.toggle("menu--open");

    ReactDOM.render(
        React.createElement("div", {}, [
            element.write ? React.createElement(UpdateForm, { key: "form", element, socket }, null) : null,
            React.createElement(PlotRenderer, { key: "plot", scheme_id: SCHEME_CONFIG.scheme_id, element }, null),
        ]),
        document.getElementById("react-menu"),
    );
};


const aggregateElements = (elements)  => {
    aggregated = { };
    for (const element of elements) {
        if (!aggregated[element.data_module])
            aggregated[element.data_module] = [];
        aggregated[element.data_module].push(element);
    }
    return aggregated;
};

const initialize = () => {
    const aggregated = aggregateElements(SCHEME_CONFIG.element);
    for (const dataModule of Object.keys(aggregated)) {
        const socket = new WebSocket(`${SOCKET_URL}/${dataModule}`);
        socket.addEventListener(
            "error",
            (ev) => console.error(`Websocker error for ${dataModule}`, ev),
        );
        socket.addEventListener("message", (ev) => {
            const msg = JSON.parse(ev.data);
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
            const cov = aggregated[dataModule].filter((element) => element.cov);
            const interval_aggregated = aggregated[dataModule].filter((element) => !element.cov && !element.single);
            const interval_single = aggregated[dataModule].filter((element) => !element.cov && element.single);
            socket.send(JSON.stringify({
                command: "cov",
                data_ids: cov.map((element) => element.data_id),
            }));
            setInterval(() => {
                socket.send(JSON.stringify({
                    command: "get",
                    data_ids: interval_aggregated.map((element) => element.data_id),
                }));
                for (const single_element of interval_single) {
                    socket.send(JSON.stringify({
                        command: "get",
                        data_ids: single_element.data_id,
                    }));
                }
            }, SCHEME_CONFIG.interval * 1000);
        });

        for (const element of aggregated[dataModule]) {
            const svgElement = document.querySelector(`#scheme svg #${element.svg_id}`);
            if (!svgElement)
                continue;
            svgElement.addEventListener("click", () => showMenu(element, socket));
            svgElement.style.cursor = "pointer";
        }
    }
};


document.querySelector("#menu-close").addEventListener("click", () => {
    document.querySelector(".menu").classList.toggle("menu--open");
});


initialize();
