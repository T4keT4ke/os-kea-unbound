<?php

/*
 * Copyright (c) 2023-2025 Deciso B.V.
 * Copyright (c) 2026 James (JameZUK)
 * BSD-2-Clause
 *
 * Search endpoints of the "All Leases" pages. Mirrors OPNsense's own Kea lease
 * listing (OPNsense\Kea\Api\LeasesController): same record decoration (interface,
 * vendor, static/dynamic, sort keys), but the records come from our `addresses`
 * action, which also lists reservations that hold no lease.
 */

namespace OPNsense\KeaUnbound\Api;

use OPNsense\Base\ApiControllerBase;
use OPNsense\Base\UserException;
use OPNsense\Core\Backend;
use OPNsense\Core\Config;

class AddressesController extends ApiControllerBase
{
    public function search4Action()
    {
        return $this->search('4');
    }

    public function search6Action()
    {
        return $this->search('6');
    }

    /**
     * Delete leases like OPNsense's own page does, but with update-ddns so Kea also
     * removes the lease's DNS records (core's action sends only the address).
     */
    public function delLease4Action($ips = null)
    {
        return $this->delLease($ips);
    }

    public function delLease6Action($ips = null)
    {
        return $this->delLease($ips);
    }

    private function delLease($ips)
    {
        if (!$this->request->isPost()) {
            return ['status' => 'error', 'message' => gettext('Invalid request method')];
        } elseif (empty($ips) || !preg_match('/^[0-9a-fA-F:.,]+$/', $ips)) {
            return ['status' => 'error', 'message' => gettext('Missing or invalid lease IP parameter')];
        }
        $results = json_decode((new Backend())->configdpRun('keaunbound lease-delete', [$ips]), true);
        if (!is_array($results)) {
            throw new UserException(gettext('Invalid backend response'));
        }
        if (!empty($results['failed'])) {
            throw new UserException(sprintf(
                gettext('Failed to delete lease(s): %s'),
                implode(', ', $results['failed'])
            ));
        }
        return ['status' => 'ok'];
    }

    private function search($family)
    {
        $selected_interfaces = $this->request->get('selected_interfaces');
        $backend = new Backend();

        $data = json_decode($backend->configdpRun('keaunbound addresses', [$family]), true) ?? [];
        $records = $data['records'] ?? [];

        $interfaces = [];
        $mac_db = json_decode($backend->configdRun('interface list macdb'), true) ?? [];

        $ifmap = [];
        foreach (Config::getInstance()->object()->interfaces->children() as $if => $if_props) {
            $ifmap[(string)$if_props->if] = [
                'descr' => (string)$if_props->descr ?: strtoupper($if),
                'key' => $if
            ];
        }

        $stats = ['active' => 0, 'inactive' => 0, 'total' => 0];

        /* fixed-width decimal-per-byte keys so the grid sorts addresses numerically */
        $byteSortKey = fn($bin) => $bin === false ? ''
            : implode('.', array_map(fn($b) => sprintf('%03d', $b), unpack('C*', $bin)));

        foreach ($records as &$record) {
            $stats['total']++;
            $stats[$record['state'] === 0 ? 'active' : 'inactive']++;

            $record['if_descr'] = '';
            $record['if_name'] = '';
            if (!empty($record['if']) && isset($ifmap[$record['if']])) {
                $record['if_descr'] = $ifmap[$record['if']]['descr'];
                $record['if_name'] = $ifmap[$record['if']]['key'];
                $interfaces[$ifmap[$record['if']]['key']] = $ifmap[$record['if']]['descr'];
            }
            $mac = strtoupper(substr(str_replace(':', '', $record['hwaddr']), 0, 6));
            $record['mac_info'] = isset($mac_db[$mac]) ? $mac_db[$mac] : '';

            $record['lease_type'] = empty($record['is_reserved']) ? 'dynamic' : 'static';
            $record['sort_address'] = $byteSortKey(@inet_pton((string)$record['address']));
            $record['sort_hwaddr'] = $byteSortKey(@hex2bin(str_replace(':', '', $record['hwaddr'])));
            $record['sort_client_id'] = $byteSortKey(@hex2bin(str_replace(':', '', $record['client_id'])));
            $record['sort_duid'] = $byteSortKey(@hex2bin(str_replace(':', '', $record['duid'])));
        }

        $response = $this->searchRecordsetBase(
            $records,
            ['if_descr', 'address', 'prefix_len', 'type', 'duid', 'iaid', 'hwaddr', 'mac_info',
                'client_id', 'valid_lifetime', 'expire', 'hostname', 'state', 'lease_type'],
            'sort_address',
            function ($key) use ($selected_interfaces) {
                return empty($selected_interfaces) || in_array($key['if_name'], $selected_interfaces);
            }
        );

        $response['stats'] = $stats;
        $response['interfaces'] = $interfaces;
        return $response;
    }
}
