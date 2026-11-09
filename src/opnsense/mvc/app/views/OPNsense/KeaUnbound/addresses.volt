{#
 # Copyright (c) 2026 James (JameZUK) - BSD-2-Clause
 #}

<script>
    $(document).ready(function () {
        $("#grid-addresses").UIBootgrid({
            search: '/api/keaunbound/addresses/search',
            options: {
                selection: false,
                multiSelect: false,
                rowCount: [20, 50, 100, 200, -1],
                formatters: {
                    // escape all free-text columns: record names/hostnames originate
                    // from DHCP clients, so they must never be rendered as raw HTML.
                    "esc": function (column, row) {
                        var v = row[column.id];
                        return $('<div>').text(v == null ? '' : v).html();
                    },
                    "type": function (column, row) {
                        var cls = row.type === 'static' ? 'label-primary' : 'label-info';
                        return '<span class="label ' + cls + '">' + $('<div>').text(row.type == null ? '' : row.type).html() + '</span>';
                    },
                    "expires": function (column, row) {
                        if (!row.expires || row.expires == 0) {
                            return '<span class="text-muted">—</span>';
                        }
                        var d = new Date(row.expires * 1000);
                        return d.toLocaleString();
                    }
                }
            }
        });
    });
</script>

<div class="content-box" style="padding: 1em;">
    <p class="text-muted" style="margin-bottom: 1em;">
        {{ lang._('All addresses Kea has handed out or reserved: active leases plus static reservations, including those whose device is offline. Use the search box to filter; click a column header to sort.') }}
    </p>
    <table id="grid-addresses" class="table table-condensed table-hover table-striped"
           data-store-selection="false">
        <thead>
            <tr>
                <th data-column-id="address" data-sortable="true" data-formatter="esc">{{ lang._('Address') }}</th>
                <th data-column-id="type" data-sortable="true" data-width="7em" data-formatter="type">{{ lang._('Type') }}</th>
                <th data-column-id="status" data-sortable="true" data-width="8em" data-formatter="esc">{{ lang._('Status') }}</th>
                <th data-column-id="hostname" data-sortable="true" data-formatter="esc">{{ lang._('Hostname') }}</th>
                <th data-column-id="hwaddr" data-sortable="true" data-formatter="esc">{{ lang._('MAC / DUID') }}</th>
                <th data-column-id="subnet" data-sortable="true" data-width="6em" data-formatter="esc">{{ lang._('Subnet') }}</th>
                <th data-column-id="expires" data-sortable="true" data-formatter="expires">{{ lang._('Expires') }}</th>
            </tr>
        </thead>
        <tbody></tbody>
    </table>
</div>
