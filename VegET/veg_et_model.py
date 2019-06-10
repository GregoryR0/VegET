"""
Defines the formula for running VegET on inputs. As defined here the function can be
run iteratively over an Earth Engine imageCollection.
"""

import ee

ee.Initialize()

# Using imageCollection.iterate() to make a collection of Soil Water Flux images.



def vegET_model(daily_imageColl, whc_grid_img, start_date):
    """
    Calculate Daily Soil Water Index (SWI)
    :param start_date: ee.Date
        First date for analysis. Used to calculate initial SWI and then removed from collection.
    :param daily_imageColl: ee.ImageCollection
        Collection of daily images with bands for ndvi, precip, pet, canopy intercept
    :param whc_grid_img: ee.Image
        Static water holding capacity image
    :return: ee.ImageCollection
        imageCollection of daily Soil Water Index
    """
    # TODO: Verify if these should be user inputs
    # Define constant variables
    VARA = ee.Number(1.25)
    VARB = ee.Number(0.2)

    # DS: moved to swi initial calculations. If that works, delete these
    # Get the date for daily_image
    #time0 = daily_image.first().get('system:time_start')

    # Create empty list for swi images to store results of iterate()
    #first_day = ee.List([
    #    ee.Image(0).set('system:time_start', time0).select([0], ['SWI'])
    #])


    def effec_precip(image):
        """
        Calculate effective precipitation
        :param image: ee.Image
            Image with precip and intercept bands

        :return: ee.Image
            Effective precipitation accounting for canopy intercept
        """

        effppt = image.expression(
            'PRECIP * (1 - (INTERCEPT/100))', {
                'PRECIP': image.select('pr'),
                'INTERCEPT': image.select('Ei')
            }
        )
        effppt = effppt.set('system:time_start', image.get('system:time_start'))

        return ee.Image(effppt)

    #    DS: This doesn't appear to be used in the demo model
    #    def intercepted_precip(image):
    #        """
    #        Calculate intercepted precipitation
    #
    #        :param image: ee.Image
    #            Image with precipitation and canopy interception bands
    #        :return: ee.Image
    #            Intercepted precipitation
    #        """
    #
    #        intppt = image.expression(
    #            'PRECIP * (INTERCEPT/100)', {
    #                'PRECIP': image.select('pr'),
    #                'INTERCEPT': image.select('Ei')
    #            }
    #        )
    #
    #        return ee.Image(intppt)

    def swi_init_calc(whc_img):
        """
        Calculate soil water index initial value. Effective precip is added in daily_swi_calc().

        :param effect_ppt_init: ee.Image
            Initial effective precipitation as calculated in effec_precip()
        :param whc_img: ee.Image
            Static image of water holding capacity

        :return: ee.Image
            Soil water index for the first day
        """
        swi_init = whc_img.multiply(0.5)

        swi_init = swi_init.set('system:time_start', effect_ppt_init.get('system:time_start'))
        return ee.Image(swi_init)

    swi_init = swi_init_calc(whc_grid_img)

    # Create SWI list for imageCollection.iterate()
    swi_list = ee.List([
        ee.Image(swi_init).set('system:time_start', swi_init.get('system:time_start')).select([0], ['SWI'])
    ])


    def daily_swi_calc(daily_image, swi_list):
        """
        Function to run imageCollection.iterate(). Takes latest value from swi_list as previous
            time-step SWI, current day whc_image and daily_image
        :param swi_list:
        :param whc_image:
        :param daily_image:
        :return:
        """
        prev_swi = ee.Image(ee.List(swi_list).get(-1))

        effective_precip = effec_precip(daily_image)

        swi_current = ee.Image(prev_swi.add(effective_precip))

        def rfi_calc(image1, image2):
            """
            Calculate runoff as swi - whc
            :param image1: ee.Image
                Soil Water Index image
            :param image2: ee.Image
                Water holding capacity image
            :return: ee.Image
                Runoff as only positive valued image
            """

            rf = image1.subtract(image2)

            # Set value to 0 if rf < 0
            rfi = rf.where(rf.lt(0), 0)

            rfi = rfi.set('system:time_start', image1.get('system:time_start'))

            return ee.Image(rfi)

        rfi = rfi_calc(swi_current, whc_grid_img)

        etasw1A = ee.Image(daily_image.select('NDVI').multiply(VARA).add(VARB)).multiply(daily_image.select(
            'PotEvap_tavg'))
        etasw1B = ee.Image(daily_image.select('NDVI').multiply(VARA).multiply(daily_image.select('PotEvap_tavg')))

        # DS This may fail since it's calling on values in multiple images
        etasw1 = etasw1A.where(daily_image.select('NDVI').gt(0.4), etasw1B)

        etasw2 = etasw1.multiply(swi_current.divide(whc_grid_img.multiply(0.5)))
        etasw3 = etasw1.where(swi_current.gt(whc_grid_img.multiply(0.5)), etasw2)
        etasw4 = swi_current.where(etasw3.gt(swi_current), etasw3)
        etasw = whc_grid_img.where(etasw4.gt(whc_grid_img), etasw4)

        swf1 = swi_current.subtract(etasw)
        whc_diff = ee.Image(whc_grid_img.subtract(etasw))

        swf = whc_diff.where(swi_current.gt(whc_grid_img), ee.Image(0.0).where(swf1.gt(0.0), swf1))

        return ee.List(swi_list).add(swf)




