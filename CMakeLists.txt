
if ( Python3_EXECUTABLE )
     # Setup testing
     set( ATS_SCRIPT
          "${CMAKE_BINARY_DIR}/integratedTests/geos_ats.sh"
        )

     add_custom_command( OUTPUT ${ATS_SCRIPT}
                         COMMAND ${CMAKE_BINARY_DIR}/bin/setup_ats_environment ${CMAKE_SOURCE_DIR}/.. ${CMAKE_BINARY_DIR} ${ATS_ARGUMENTS}
                         WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
                       )

     add_custom_target( ats_environment
                        DEPENDS geosx_python_tools
                        DEPENDS ${ATS_SCRIPT} )

     add_custom_target( ats_run
                        COMMAND ${CMAKE_BINARY_DIR}/integratedTests/geos_ats.sh
                        WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
                        DEPENDS ats_environment
                      )

     add_custom_target( ats_clean
                        COMMAND ${CMAKE_BINARY_DIR}/integratedTests/geos_ats.sh -a veryclean
                        WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
                        DEPENDS ats_environment
                      )

     add_custom_target( ats_rebaseline
                        COMMAND ${CMAKE_BINARY_DIR}/integratedTests/geos_ats.sh -a rebaseline
                        WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
                        DEPENDS ats_environment
                      )

     add_custom_target( ats_rebaseline_failed
                        COMMAND ${CMAKE_BINARY_DIR}/integratedTests/geos_ats.sh -a rebaselinefailed
                        WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
                        DEPENDS ats_environment
                      )

else()
     message(WARNING "GEOS ATS requires Python >= 3.7.")
     message(WARNING "Try setting Python3_ROOT_DIR and/or Python3_EXECUTABLE in your host config.")
endif()


# Python formatting
if ( ENABLE_YAPF )
     set( integrated_tests_python_sources )
     file( GLOB_RECURSE integrated_tests_python_sources "${CMAKE_SOURCE_DIR}/../integratedTests/*.py" )
     set( integrated_tests_ats_sources )
     file( GLOB_RECURSE integrated_tests_ats_sources "${CMAKE_SOURCE_DIR}/../integratedTests/*.ats" )

     blt_add_code_checks( PREFIX  integrated_tests_yapf_style
                          SOURCES ${integrated_tests_python_sources} ${integrated_tests_ats_sources} ${CMAKE_SOURCE_DIR}/coreComponents/dummy.cpp
                          YAPF_CFG_FILE ${PROJECT_SOURCE_DIR}/yapf.cfg )
endif()

