<?php

/*
 * Copyright (c) 2026 James (JameZUK)
 * BSD-2-Clause
 */

namespace OPNsense\KeaUnbound\Api;

/**
 * Search endpoint for the Addresses page: Kea leases + reservations, same
 * bootgrid contract as the Records page (only the configd action differs).
 */
class AddressesController extends RecordsController
{
    protected $configdAction = 'keaunbound addresses';
}
