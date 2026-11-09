{#
 # Copyright (c) 2026 James (JameZUK) - BSD-2-Clause
 #}

<script>
    $(document).ready(function() {
        var data_get_map = {'frm_general': "/api/keaunbound/general/get"};
        mapDataToFormUI(data_get_map).done(function(data) {
            formatTokenizersUI();
            $('.selectpicker').selectpicker('refresh');
        });

        // GSS-TSIG keytab: shown as text only, never read back; upload goes through a
        // root-run backend action that validates the file.
        function loadKeytabStatus() {
            ajaxCall("/api/keaunbound/keytab/status", {}, function(d) {
                var $s = $("#keytab_status").empty();
                if (!d || !d.exists) {
                    $s.text("{{ lang._('No keytab installed.') }}");
                    return;
                }
                var when = new Date(d.modified * 1000).toLocaleString('sv-SE');
                $s.append($("<div>").text(d.path + " (" + d.size + " bytes, " + when + ")"));
                $.each(d.principals || [], function(i, p) {
                    $s.append($("<div>").text(p.principal + " (kvno " + p.kvno + ")"));
                });
            });
        }
        loadKeytabStatus();
        $("#keytab_upload").click(function() {
            var file = $("#keytab_file")[0].files[0];
            if (!file) { return; }
            var reader = new FileReader();
            reader.onload = function() {
                var bytes = new Uint8Array(reader.result), bin = "";
                for (var i = 0; i < bytes.length; i++) { bin += String.fromCharCode(bytes[i]); }
                $("#keytab_progress").addClass("fa fa-spinner fa-pulse");
                ajaxCall("/api/keaunbound/keytab/upload", {keytab_b64: btoa(bin)}, function(d) {
                    $("#keytab_progress").removeClass("fa fa-spinner fa-pulse");
                    $("#keytab_msg").text(d && d.status === 'ok' ? "{{ lang._('Keytab installed.') }}"
                        : ((d && d.message) || "{{ lang._('Upload failed.') }}"));
                    $("#keytab_file").val("");
                    loadKeytabStatus();
                });
            };
            reader.readAsArrayBuffer(file);
        });

        // Save
        $("#saveAct").click(function() {
            saveFormToEndpoint("/api/keaunbound/general/set", 'frm_general', function() {
                $("#saveAct_progress").addClass("fa fa-spinner fa-pulse");
                ajaxCall("/api/keaunbound/service/reconfigure", {}, function(data, status) {
                    $("#saveAct_progress").removeClass("fa fa-spinner fa-pulse");
                });
            });
        });
    });
</script>

<div class="content-box" style="padding-bottom: 1.5em; margin-bottom: 1em;">
    <div class="col-md-12">
        <h3>{{ lang._('GSS-TSIG keytab') }}</h3>
        <p class="text-muted">
            {{ lang._('Upload the keytab exported with ktpass on the domain controller. It is stored on the firewall only (mode 600), never in the configuration, and never shown again. Path and name come from the settings below.') }}
        </p>
        <div id="keytab_status" class="text-muted" style="margin-bottom: 0.5em;"></div>
        <input type="file" id="keytab_file" style="display: inline-block;"/>
        <button class="btn btn-default" id="keytab_upload" type="button">
            <b>{{ lang._('Upload keytab') }}</b> <i id="keytab_progress"></i>
        </button>
        <div id="keytab_msg" style="margin-top: 0.5em;"></div>
        <hr/>
    </div>
</div>
<div class="content-box" style="padding-bottom: 1.5em;">
    {{ partial("layout_partials/base_form", ['fields': generalForm, 'id': 'frm_general']) }}
    <div class="col-md-12">
        <hr/>
        <button class="btn btn-primary" id="saveAct" type="button">
            <b>{{ lang._('Save') }}</b> <i id="saveAct_progress"></i>
        </button>
    </div>
</div>
