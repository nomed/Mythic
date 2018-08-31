var payloads = []; //all services data
var show_autogenerated = false;
var payloads_table = new Vue({
    el: '#payloads_table',
    data: {
        payloads,
        show_autogenerated
    },
    methods: {
        delete_button: function(p){
		$( '#payloadDeleteModal' ).modal('show');
		$( '#payloadDeleteSubmit' ).unbind('click').click(function(){
			httpGetAsync("{{http}}://{{links.server_ip}}:{{links.server_port}}{{links.api_base}}/payloads/" + p.uuid, delete_callback, "DELETE", null);
		});
        },
	show_uuid_button: function(p){
		alert(p.uuid);
	}
    },
    delimiters: ['[[',']]']
});
function delete_callback(response){
	data = JSON.parse(response);
	if(data['status'] == 'success'){
		var i = 0;
		for( i = 0; i < payloads.length; i++){
		    if(payloads[i].uuid == data['uuid']){
		        break;
		    }
		}
		payloads.splice(i, 1);
	}
	else{
		//there was an error, so we should tell the user
		alert("Error: " + data['error']);
	}
}
function startwebsocket_payloads(){
	var ws = new WebSocket('{{ws}}://{{links.server_ip}}:{{links.server_port}}/ws/payloads');
	ws.onmessage = function(event){
		if(event.data != ""){
			pdata = JSON.parse(event.data);
			payloads.push(pdata);
			
		}
	}
	ws.onclose = function(){
		//console.log("payloads socket closed");
	}
	ws.onerror = function(){
		//console.log("payloads socket errored");
	}
	ws.onopen = function(){
		//console.log("payloads socket opened");
	}
}
startwebsocket_payloads();
function toggle_all_button(){
    payloads_table.show_autogenerated = !payloads_table.show_autogenerated;
}
