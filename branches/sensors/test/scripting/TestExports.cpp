#include "scripting/exports.h"

#include <boost/test/unit_test.hpp>

BOOST_AUTO_TEST_SUITE( test_opennero )

BOOST_AUTO_TEST_CASE( test_exports )
{
    OpenNero::scripting::ExportScripts();
}

BOOST_AUTO_TEST_SUITE_END()