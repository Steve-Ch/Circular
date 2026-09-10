function initAdminStats() {
    console.log("Admin stats script initialized!");

    if (window.location.pathname === '/admin/' || window.location.pathname === '/admin') {
        
        // Inject custom styles for compact card dimensions (4 per row) and hover effects
        if (!document.getElementById('custom-dashboard-card-styles')) {
            const styleEl = document.createElement('style');
            styleEl.id = 'custom-dashboard-card-styles';
            styleEl.innerHTML = `
                .custom-stat-card {
                    border-radius: 8px;
                    padding: 16px 20px;
                    color: #ffffff;
                    position: relative;
                    overflow: hidden;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.07);
                    transition: all 0.3s ease;
                    min-height: 105px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                .custom-stat-card:hover {
                    transform: translateY(-4px);
                    box-shadow: 0 10px 20px rgba(0,0,0,0.15);
                }
                .custom-stat-card .stat-label {
                    font-size: 0.7rem;
                    font-weight: 700;
                    text-transform: uppercase;
                    letter-spacing: 0.8px;
                    opacity: 0.85;
                    margin-bottom: 4px;
                }
                .custom-stat-card .stat-value {
                    font-size: 1.8rem;
                    font-weight: 700;
                    line-height: 1.2;
                    margin-bottom: 0;
                }
                .custom-stat-card .stat-sub {
                    font-size: 0.75rem;
                    opacity: 0.85;
                    margin-top: 3px;
                    font-weight: 500;
                }
                .custom-stat-card .stat-icon {
                    font-size: 2.8rem;
                    opacity: 0.25;
                    line-height: 1;
                }
            `;
            document.head.appendChild(styleEl);
        }

        function getLocalDateString(dateObj) {
            const year = dateObj.getFullYear();
            const month = String(dateObj.getMonth() + 1).padStart(2, '0');
            const day = String(dateObj.getDate()).padStart(2, '0');
            return `${year}-${month}-${day}`;
        }

        function getDefaultDates() {
            const today = new Date();
            const yesterday = new Date();
            yesterday.setDate(today.getDate() - 1);
            return {
                todayStr: getLocalDateString(today),
                yesterdayStr: getLocalDateString(yesterday)
            };
        }

        function fetchStats(startDate, endDate) {
            let url = '/admin/dashboard-stats/';
            if (startDate && endDate) {
                url += `?start_date=${startDate}&end_date=${endDate}`;
            }

            fetch(url)
                .then(response => {
                    if (response.status === 403) throw new Error('Not a superuser');
                    return response.json();
                })
                .then(data => {
                    if (data.error) return;
                    renderUI(data, startDate, endDate);
                })
                .catch(err => console.error('Stats error:', err));
        }

        function renderUI(data, currentStart, currentEnd) {
            let container = document.getElementById('custom-dashboard-stats');
            
            const isHidden = sessionStorage.getItem('admin_stats_hidden') === 'true';

            if (!container) {
                container = document.createElement('div');
                container.id = 'custom-dashboard-stats';
                container.style.cssText = "margin: 20px; position: relative; z-index: 1; display: block; clear: both;";
                
                let targetDiv = document.querySelector('.content .container-fluid') 
                             || document.querySelector('.content') 
                             || document.querySelector('.content-wrapper') 
                             || document.getElementById('content-main') 
                             || document.getElementById('content') 
                             || document.querySelector('main') 
                             || document.body;

                if (targetDiv === document.body) {
                    targetDiv.insertBefore(container, targetDiv.firstChild);
                } else {
                    targetDiv.prepend(container);
                }
            }

            const { todayStr, yesterdayStr } = getDefaultDates();
            const sDate = currentStart || yesterdayStr;
            const eDate = currentEnd || todayStr;

            const formattedProfit = parseFloat(data.delivery_profit || 0).toLocaleString('en-US', {
                minimumFractionDigits: 2, 
                maximumFractionDigits: 2
            });

            container.innerHTML = `
                <div class="row">
                    <div class="col-12">
                        <div class="card card-outline card-primary mb-3 shadow-sm" style="border-radius: 8px;">
                            <div class="card-header border-0 d-flex align-items-center flex-wrap py-3">
                                <h3 class="card-title mr-4 font-weight-bold" style="font-size: 1.1rem;">
                                    <i class="fas fa-chart-line mr-2 text-primary"></i> Platform Statistics
                                </h3>
                                <div class="d-flex align-items-center flex-wrap ml-auto">
                                    <label class="mr-2 mb-0 font-weight-normal text-muted">From:</label>
                                    <input type="date" id="stats-start-date" class="form-control form-control-sm mr-3" style="width: auto; border-radius: 6px;" value="${sDate}">
                                    
                                    <label class="mr-2 mb-0 font-weight-normal text-muted">To:</label>
                                    <input type="date" id="stats-end-date" class="form-control form-control-sm mr-3" style="width: auto; border-radius: 6px;" value="${eDate}">
                                    
                                    <button id="btn-update-stats" class="btn btn-sm btn-primary px-3 shadow-sm mr-2" style="border-radius: 6px;">Filter</button>
                                    <button id="btn-toggle-stats" class="btn btn-sm btn-outline-secondary px-2 shadow-sm" style="border-radius: 6px;" title="Toggle Visibility">
                                        <i class="fas ${isHidden ? 'fa-eye' : 'fa-eye-slash'}"></i> ${isHidden ? 'Show Cards' : 'Hide Cards'}
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div id="stats-cards-grid" class="row" style="display: ${isHidden ? 'none' : 'flex'};">
                    <!-- Total Users -->
                    <div class="col-xl-3 col-lg-3 col-md-6 col-12 mb-3">
                        <div class="custom-stat-card" style="background-color: #2c3e50;">
                            <div>
                                <div class="stat-label">Total Users</div>
                                <div class="stat-value">${data.total_users ?? 0}</div>
                                <div class="stat-sub">+${data.new_users} new users in range</div>
                            </div>
                            <div class="stat-icon">
                                <i class="fas fa-users"></i>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Successful Deliveries -->
                    <div class="col-xl-3 col-lg-3 col-md-6 col-12 mb-3">
                        <div class="custom-stat-card" style="background-color: #27ae60;">
                            <div>
                                <div class="stat-label">Successful Deliveries</div>
                                <div class="stat-value">${data.successful_deliveries}</div>
                                <div class="stat-sub">Completed drop-offs</div>
                            </div>
                            <div class="stat-icon">
                                <i class="fas fa-truck-loading"></i>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Delivery Fee Profit -->
                    <div class="col-xl-3 col-lg-3 col-md-6 col-12 mb-3">
                        <div class="custom-stat-card" style="background-color: #3498db;">
                            <div>
                                <div class="stat-label">Delivery Fee Profit</div>
                                <div class="stat-value">₦${formattedProfit}</div>
                                <div class="stat-sub">Accumulated revenue</div>
                            </div>
                            <div class="stat-icon">
                                <i class="fas fa-money-bill-wave"></i>
                            </div>
                        </div>
                    </div>

                    <!-- Supported Estates -->
                    <div class="col-xl-3 col-lg-3 col-md-6 col-12 mb-3">
                        <div class="custom-stat-card" style="background-color: #e74c3c;">
                            <div>
                                <div class="stat-label">Supported Estates</div>
                                <div class="stat-value">${data.supported_estates ?? 0}</div>
                                <div class="stat-sub">Active service zones</div>
                            </div>
                            <div class="stat-icon">
                                <i class="fas fa-city"></i>
                            </div>
                        </div>
                    </div>

                    <!-- Onboarded Merchants -->
                    <div class="col-xl-3 col-lg-3 col-md-6 col-12 mb-3">
                        <div class="custom-stat-card" style="background-color: #8e44ad;">
                            <div>
                                <div class="stat-label">Onboarded Merchants</div>
                                <div class="stat-value">${data.onboarded_merchants ?? 0}</div>
                                <div class="stat-sub">Active store partners</div>
                            </div>
                            <div class="stat-icon">
                                <i class="fas fa-store"></i>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            document.getElementById('btn-update-stats').addEventListener('click', function(e) {
                e.preventDefault();
                const s = document.getElementById('stats-start-date').value;
                const e_date = document.getElementById('stats-end-date').value;
                fetchStats(s, e_date);
            });

            document.getElementById('btn-toggle-stats').addEventListener('click', function(e) {
                e.preventDefault();
                const grid = document.getElementById('stats-cards-grid');
                const currentlyHidden = grid.style.display === 'none';
                
                if (currentlyHidden) {
                    grid.style.display = 'flex';
                    sessionStorage.setItem('admin_stats_hidden', 'false');
                    this.innerHTML = '<i class="fas fa-eye-slash"></i> Hide Cards';
                } else {
                    grid.style.display = 'none';
                    sessionStorage.setItem('admin_stats_hidden', 'true');
                    this.innerHTML = '<i class="fas fa-eye"></i> Show Cards';
                }
            });
        }

        const { todayStr, yesterdayStr } = getDefaultDates();
        fetchStats(yesterdayStr, todayStr);
    }
}

setTimeout(function() {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAdminStats);
    } else {
        initAdminStats();
    }
}, 500);