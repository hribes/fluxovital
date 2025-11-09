let map;
let directionsService;
let directionsRenderer;


function iniciarMapa() {
    map = new google.maps.Map(document.getElementById("map"),{
        center:{
            lat: -22.2349,
            lng: -49.9709
        },
        zoom: 14,
        mapId: "teste"
    });

    directionsService = new google.maps.DirectionsService();
    directionsRenderer = new google.maps.DirectionsRenderer();

    dm = new google.maps.drawing.DrawingManager({
        drawingMode: google.maps.drawing.OverlayType.MARKER,
        drawingControl:true,
        drawingControlOptions:{
            position: google.maps.ControlPosition.TOP_CENTER,
            drawingModes:["polyline", "marker"]
        }
    });

}