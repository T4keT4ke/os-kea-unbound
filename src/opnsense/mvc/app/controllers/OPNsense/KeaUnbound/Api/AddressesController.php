<?php

/*
 * Copyright (c) 2026 James (JameZUK)
 * BSD-2-Clause
 */

namespace OPNsense\KeaUnbound\Api;

use OPNsense\Core\Backend;

/**
 * Search endpoints for the "All Leases" pages: Kea leases + reservations per
 * family, same bootgrid contract as the Records page.
 */
class AddressesController extends RecordsController
{
    private $family = '4';

    protected function fetchRows()
    {
        return (string)(new Backend())->configdpRun('keaunbound addresses', [$this->family]);
    }

    public function search4Action()
    {
        $this->family = '4';
        return $this->searchAction();
    }

    public function search6Action()
    {
        $this->family = '6';
        return $this->searchAction();
    }
}
