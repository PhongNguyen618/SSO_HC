
                            function toggleBannerDaysRow() {
                                const mode = document.getElementById('rules_banner_mode').value;
                                const group = document.getElementById('banner_reset_days_group');
                                if (mode === 'days') {
                                    group.style.display = 'block';
                                } else {
                                    group.style.display = 'none';
                                }
                            }
                        